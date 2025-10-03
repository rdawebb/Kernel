#!/usr/bin/env python3
"""
Simple IMAP connection test script.
Tests connection to email server without fetching emails.
"""

import sys
from utils.config import load_config
from core.imap_client import connect_to_imap

def test_imap_connection():
    """Test IMAP connection and return detailed status"""
    
    print("🔌 Testing IMAP connection...")
    print("-" * 40)
    
    try:
        # Load configuration
        print("📋 Loading configuration...")
        config = load_config()
        print(f"   Server: {config['imap_server']}")
        print(f"   Port: {config['imap_port']}")
        print(f"   SSL: {config['imap_use_ssl']}")
        print(f"   Email: {config['email']}")
        print()
        
        # Test connection
        print("🔐 Attempting connection...")
        mail = connect_to_imap(config)
        
        if mail:
            print("✅ Connection successful!")
            
            # Get some basic info about the connection
            try:
                # Check if we can access inbox
                status, messages = mail.search(None, 'ALL')
                if status == 'OK':
                    email_count = len(messages[0].split()) if messages[0] else 0
                    print(f"📧 Inbox contains {email_count} messages")
                
                # Get mailbox list
                status, mailboxes = mail.list()
                if status == 'OK':
                    print(f"📁 Found {len(mailboxes)} mailboxes")
                    
            except Exception as e:
                print(f"⚠️  Connected but couldn't get mailbox info: {e}")
            
            # Clean up
            try:
                mail.logout()
                print("🚪 Disconnected cleanly")
            except:
                pass
                
            return True
            
        else:
            print("❌ Connection failed!")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_imap_connection()
    
    if success:
        print("\n🎉 IMAP connection test passed!")
        print("You can now use 'python cli.py list' to fetch emails.")
        sys.exit(0)
    else:
        print("\n💥 IMAP connection test failed!")
        print("Please check your .env file settings.")
        sys.exit(1)
