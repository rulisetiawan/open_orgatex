"""
Sinkronisasi Batch dari Database ke FTP Controller OrgaTEX (192.168.1.95)
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./open_orgatex"))

from open_orgatex.backend.services.ftp_sync_service import sync_all_batches_to_ftp

if __name__ == "__main__":
    sync_all_batches_to_ftp()
