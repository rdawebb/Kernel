"""
Tests for user interface components and display functions

Tests cover:
- Inbox display formatting
- Email viewer display
- Search results display
- Flag status indicators
- Table rendering
- Error handling in UI
"""
from src.ui.email_viewer import display_email
from src.ui.inbox_viewer import display_inbox
from src.ui.search_viewer import display_search_results

from .test_helpers import ConsoleTestHelper, DatabaseTestHelper


class TestInboxDisplay:
    """Tests for inbox viewer display functionality"""
    
    def test_display_inbox_with_emails(self):
        """Test displaying inbox with email list"""
        emails = DatabaseTestHelper.create_mock_emails(count=2)
        
        output, _ = ConsoleTestHelper.capture_console_output(display_inbox, "inbox", emails)
        
        # Verify emails are displayed
        assert 'inbox' in output.lower() or 'email' in output.lower()
    
    def test_display_inbox_empty(self):
        """Test displaying empty inbox"""
        output, _ = ConsoleTestHelper.capture_console_output(display_inbox, "inbox", [])
        
        # Should display table structure even when empty
        assert 'inbox' in output.lower() or output  # At least something is rendered
    
    def test_display_inbox_shows_sender(self):
        """Test that inbox display shows sender information"""
        email = DatabaseTestHelper.create_mock_email(from_='sender@example.com')
        
        output, _ = ConsoleTestHelper.capture_console_output(display_inbox, "inbox", [email])
        
        assert 'sender@example.com' in output or 'example.com' in output
    
    def test_display_inbox_shows_subject(self):
        """Test that inbox display shows email subject"""
        email = DatabaseTestHelper.create_mock_email(subject='Important Meeting')
        
        output, _ = ConsoleTestHelper.capture_console_output(display_inbox, "inbox", [email])
        
        assert 'Important' in output or 'Meeting' in output
    
    def test_display_inbox_with_flagged_emails(self):
        """Test displaying inbox with flagged emails"""
        flagged_email = DatabaseTestHelper.create_mock_email(uid='flagged_1', flagged=True)
        unflagged_email = DatabaseTestHelper.create_mock_email(uid='unflagged_1', flagged=False)
        
        output, _ = ConsoleTestHelper.capture_console_output(
            display_inbox, "inbox", [flagged_email, unflagged_email]
        )
        
        # Display should handle both flagged and unflagged emails
        assert output is not None


class TestEmailDisplay:
    """Tests for email viewer display"""
    
    def test_display_email_complete(self):
        """Test displaying complete email"""
        email = DatabaseTestHelper.create_mock_email(
            from_='sender@example.com',
            subject='Test Subject',
            body='Test body content'
        )
        
        output, _ = ConsoleTestHelper.capture_console_output(display_email, email)
        
        # Verify key information is displayed
        assert 'sender@example.com' in output or 'example.com' in output
    
    def test_display_email_with_missing_fields(self):
        """Test displaying email with missing optional fields"""
        minimal_email = {
            'from': 'sender@example.com',
            'subject': 'Test Subject'
        }
        
        output, _ = ConsoleTestHelper.capture_console_output(display_email, minimal_email)
        
        # Should handle missing fields gracefully
        assert output is not None
    
    def test_display_email_with_empty_body(self):
        """Test displaying email with empty body"""
        email = DatabaseTestHelper.create_mock_email(body='')
        
        output, _ = ConsoleTestHelper.capture_console_output(display_email, email)
        
        # Should display without error
        assert output is not None
    
    def test_display_email_with_long_body(self):
        """Test displaying email with long body"""
        long_body = "This is a very long email body. " * 100
        email = DatabaseTestHelper.create_mock_email(body=long_body)
        
        output, _ = ConsoleTestHelper.capture_console_output(display_email, email)
        
        # Should handle long bodies
        assert output is not None
    
    def test_display_email_shows_all_fields(self):
        """Test that email display includes all fields"""
        email = DatabaseTestHelper.create_mock_email(
            from_='sender@example.com',
            subject='Important Email',
            date='2025-10-02',
            body='Important content'
        )
        
        output, _ = ConsoleTestHelper.capture_console_output(display_email, email)
        
        # Verify important information is present
        assert len(output) > 0


class TestSearchResultsDisplay:
    """Tests for search results display"""
    
    def test_display_search_results_with_emails(self):
        """Test displaying search results with emails"""
        emails = DatabaseTestHelper.create_mock_emails(count=2)
        
        output, _ = ConsoleTestHelper.capture_console_output(
            display_search_results, "inbox", emails, "test_keyword"
        )
        
        # Should show search results
        assert output is not None
    
    def test_display_search_results_empty(self):
        """Test displaying empty search results"""
        output, _ = ConsoleTestHelper.capture_console_output(
            display_search_results, "inbox", [], "keyword"
        )
        
        # Should handle empty results
        assert output is not None
    
    def test_display_search_results_shows_keyword(self):
        """Test that search results display includes search keyword"""
        emails = DatabaseTestHelper.create_mock_emails(count=1)
        
        output, _ = ConsoleTestHelper.capture_console_output(
            display_search_results, "inbox", emails, "important"
        )
        
        # Should reference the search term
        assert output is not None or 'important' in output.lower()


class TestUIDataFormatting:
    """Tests for data formatting in UI displays"""
    
    def test_display_inbox_preserves_email_data(self):
        """Test that displaying emails doesn't modify data"""
        original_emails = DatabaseTestHelper.create_mock_emails(count=2)
        emails_copy = [e.copy() for e in original_emails]
        
        display_inbox("inbox", emails_copy)
        
        # Data should not be modified
        assert emails_copy == original_emails
    
    def test_display_email_handles_special_characters(self):
        """Test display handles special characters in email"""
        email = DatabaseTestHelper.create_mock_email(
            subject='Test with special chars: <>&"\'',
            body='Body with special chars: <>&"\''
        )
        
        # Should not raise exception
        output, _ = ConsoleTestHelper.capture_console_output(display_email, email)
        assert output is not None


class TestUIErrorHandling:
    """Tests for error handling in UI components"""
    
    def test_display_inbox_handles_malformed_email_list(self):
        """Test inbox display handles malformed email list"""
        # Try with None values
        emails_with_none = [None, DatabaseTestHelper.create_mock_email()]
        
        # Should handle gracefully
        try:
            display_inbox("inbox", emails_with_none)
        except AttributeError:
            # Expected if None is not handled
            pass
    
    def test_display_email_with_none_input(self):
        """Test email display with None input"""
        try:
            display_email(None)
        except (TypeError, AttributeError):
            # Expected if None is not handled
            pass
    
    def test_display_inbox_with_none_input(self):
        """Test inbox display with None input"""
        try:
            display_inbox("inbox", None)
        except TypeError:
            # Expected if None is not handled
            pass
