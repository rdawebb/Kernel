#!/usr/bin/env python3
"""
Simple IMAP connection test script.
Tests connection to email server without fetching emails.
"""

import unittest
from unittest.mock import patch, MagicMock
import imaplib
import tempfile
import os
import sys

from src.quiet_mail.utils.config import load_config
from src.quiet_mail.core.imap_client import connect_to_imap

def test_imap_connection():
    """Test IMAP connection and return detailed status"""
    
    print("🔌 Testing IMAP connection...")
    
    try:
        # Load configuration
        config = load_config()
        
        # Test connection
        server = connect_to_imap(config)
        if server:
            print("✅ Successfully connected to IMAP server!")
            print(f"   Server: {config['imap_server']}:{config['imap_port']}")
            print(f"   Email: {config['email']}")
            print(f"   SSL: {'Yes' if config['imap_use_ssl'] else 'No'}")
            
            # Test authentication by selecting INBOX
            try:
                status, _ = server.select('INBOX')
                if status == 'OK':
                    print("✅ Successfully authenticated and selected INBOX!")
                else:
                    print("⚠️  Connected but failed to select INBOX")
            except Exception as e:
                print(f"⚠️  Connected but authentication issue: {e}")
            
            # Clean up
            try:
                server.logout()
            except:
                pass
                
            # Use assert instead of return for pytest
            assert True, "IMAP connection successful"
            
        else:
            print("❌ Connection failed!")
            assert False, "IMAP connection failed"
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        assert False, f"IMAP connection test failed: {e}"

if __name__ == "__main__":
    try:
        test_imap_connection()
        print("\n🎉 IMAP connection test passed!")
        print("You can now use 'python cli.py list' to fetch emails.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n💥 IMAP connection test failed: {e}")
        print("Please check your .env file settings.")
        sys.exit(1)
