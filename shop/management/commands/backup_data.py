import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Create a backup zip with a consistent copy of the SQLite database and the uploaded media "
        "files. Old backups are deleted, keeping the newest --keep ones. Run it daily from cron."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dir', default=str(settings.BASE_DIR.parent / 'techmobi-backups'),
                            help="Folder for the backups (default: 'techmobi-backups' next to the project folder, "
                                 "outside the website's files).")
        parser.add_argument('--keep', type=int, default=14, help="How many backups to keep (default 14).")
        parser.add_argument('--no-media', action='store_true', help="Back up only the database.")

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if 'sqlite3' not in db['ENGINE']:
            raise CommandError("backup_data only supports SQLite. Use your database's own backup tool.")
        if not Path(str(db['NAME'])).is_file():
            raise CommandError(f"Database file not found: {db['NAME']}")
        if options['keep'] < 1:
            raise CommandError("--keep must be at least 1.")

        backup_dir = Path(options['dir'])
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.chmod(0o700)
        stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        target = backup_dir / f'techmobi-backup-{stamp}.zip'

        with tempfile.TemporaryDirectory() as tmp:
            db_copy = Path(tmp) / 'db.sqlite3'
            # sqlite3's backup API gives a consistent snapshot even while the site is being used.
            source = sqlite3.connect(str(db['NAME']))
            dest = sqlite3.connect(str(db_copy))
            try:
                source.backup(dest)
            finally:
                dest.close()
                source.close()

            with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.write(db_copy, 'db.sqlite3')
                media_root = Path(settings.MEDIA_ROOT)
                media_files = 0
                if not options['no_media'] and media_root.is_dir():
                    for path in sorted(media_root.rglob('*')):
                        if path.is_file():
                            archive.write(path, Path('media') / path.relative_to(media_root))
                            media_files += 1
        target.chmod(0o600)

        # Keep only the newest backups.
        old = sorted(backup_dir.glob('techmobi-backup-*.zip'))[:-options['keep']]
        for path in old:
            path.unlink()

        size_mb = target.stat().st_size / 1024 / 1024
        self.stdout.write(self.style.SUCCESS(
            f"Backup saved: {target} ({size_mb:.1f} MB, {media_files} media files). "
            f"Removed {len(old)} old backup(s)."))
