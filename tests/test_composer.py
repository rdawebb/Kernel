"""
Tests for email composer functionality

Tests cover:
- Email composition workflow
- Input validation
- Email sending
- Draft saving
- Schedule sending
"""
from unittest.mock import patch, MagicMock

from src.ui.composer import compose_email


class TestComposeEmailWorkflow:
    """Tests for email composition workflow"""
    
    @patch('src.ui.composer.prompt_send_later', return_value=None)
    @patch('src.ui.composer.send_email_now')
    @patch('src.ui.composer.show_send_success')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_basic_workflow(self, mock_prompt_details, mock_show_preview,
                                         mock_confirm, mock_show_success, mock_send,
                                         mock_prompt_later):
        """Test basic email composition workflow"""
        mock_prompt_details.return_value = {
            'recipient': 'recipient@example.com',
            'subject': 'Test Subject',
            'body': 'Test body'
        }
        mock_confirm.return_value = True
        mock_send.return_value = (True, None)
        
        result = compose_email()
        assert result is True
    
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_empty_recipient(self, mock_prompt_details):
        """Test composition with empty recipient"""
        mock_prompt_details.return_value = None
        
        result = compose_email()
        
        # Should reject empty recipient
        assert result is False
    
    @patch('src.ui.composer.save_as_draft')
    @patch('src.ui.composer.show_draft_saved')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_invalid_recipient(self, mock_prompt_details, mock_show_preview,
                                            mock_confirm, mock_show_draft, mock_save_draft):
        """Test composition with invalid email address"""
        mock_prompt_details.return_value = {
            'recipient': 'invalid-email',
            'subject': 'Test',
            'body': 'Body'
        }
        mock_confirm.return_value = False
        
        result = compose_email()
        
        # Should handle gracefully
        assert result is False or result is None


class TestComposeEmailValidation:
    """Tests for email composition validation"""
    
    @patch('src.ui.composer.prompt_send_later', return_value=None)
    @patch('src.ui.composer.send_email_now')
    @patch('src.ui.composer.show_send_success')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_empty_subject_confirm(self, mock_prompt_details, mock_show_preview,
                                                 mock_confirm, mock_show_success, mock_send,
                                                 mock_prompt_later):
        """Test allowing composition with empty subject when confirmed"""
        mock_prompt_details.return_value = {
            'recipient': 'recipient@example.com',
            'subject': '',  # empty subject
            'body': 'Body text'
        }
        mock_confirm.return_value = True
        mock_send.return_value = (True, None)
        
        result = compose_email()
        assert result is True
    
    @patch('src.ui.composer.save_as_draft')
    @patch('src.ui.composer.show_draft_saved')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_empty_subject_reject(self, mock_prompt_details, mock_show_preview,
                                               mock_confirm, mock_show_draft, mock_save_draft):
        """Test rejecting composition with empty subject"""
        mock_prompt_details.return_value = {
            'recipient': 'test@example.com',
            'subject': '',
            'body': 'Test body'
        }
        mock_confirm.return_value = False
        
        result = compose_email()
        assert result is False or result is None
    
    @patch('src.ui.composer.prompt_send_later', return_value=None)
    @patch('src.ui.composer.send_email_now')
    @patch('src.ui.composer.show_send_success')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_empty_body_confirm(self, mock_prompt_details, mock_show_preview,
                                             mock_confirm, mock_show_success, mock_send,
                                             mock_prompt_later):
        """Test allowing composition with empty body when confirmed"""
        mock_prompt_details.return_value = {
            'recipient': 'recipient@example.com',
            'subject': 'Subject',
            'body': '',  # empty body
        }
        mock_confirm.return_value = True
        mock_send.return_value = (True, None)
        
        result = compose_email()
        assert result is True


class TestComposeSendActions:
    """Tests for send/schedule/draft actions"""
    
    @patch('src.ui.composer.prompt_send_later', return_value=None)
    @patch('src.ui.composer.send_email_now')
    @patch('src.ui.composer.show_send_success')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_send_now(self, mock_prompt_details, mock_show_preview,
                                   mock_confirm, mock_show_success, mock_send,
                                   mock_prompt_later):
        """Test sending email immediately"""
        mock_prompt_details.return_value = {
            'recipient': 'recipient@example.com',
            'subject': 'Subject',
            'body': 'Body'
        }
        mock_confirm.return_value = True
        mock_send.return_value = (True, None)
        
        result = compose_email()
        assert result is True
    
    @patch('src.ui.composer.save_as_draft')
    @patch('src.ui.composer.show_draft_saved')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_cancel(self, mock_prompt_details, mock_show_preview,
                                 mock_confirm, mock_show_draft, mock_save_draft):
        """Test canceling email composition"""
        mock_prompt_details.return_value = {
            'recipient': 'recipient@example.com',
            'subject': 'Subject',
            'body': 'Body'
        }
        mock_confirm.return_value = False  # user cancels
        
        result = compose_email()
        assert result is False or result is None


class TestComposeMultilineBody:
    """Tests for multiline body handling"""
    
    @patch('src.ui.composer.prompt_send_later', return_value=None)
    @patch('src.ui.composer.send_email_now')
    @patch('src.ui.composer.show_send_success')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_multiline_body(self, mock_prompt_details, mock_show_preview,
                                         mock_confirm, mock_show_success, mock_send,
                                         mock_prompt_later):
        """Test composing email with multiline body"""
        mock_prompt_details.return_value = {
            'recipient': 'recipient@example.com',
            'subject': 'Multi-line Test',
            'body': 'Line 1\nLine 2\nLine 3'
        }
        mock_confirm.return_value = True
        mock_send.return_value = (True, None)
        
        result = compose_email()
        assert result is True
    
    @patch('src.ui.composer.prompt_send_later', return_value=None)
    @patch('src.ui.composer.send_email_now')
    @patch('src.ui.composer.show_send_success')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_body_with_empty_lines(self, mock_prompt_details, mock_show_preview,
                                                mock_confirm, mock_show_success, mock_send,
                                                mock_prompt_later):
        """Test composing email with body containing empty lines"""
        mock_prompt_details.return_value = {
            'recipient': 'recipient@example.com',
            'subject': 'Test with Blank Lines',
            'body': 'Line 1\n\nLine 3'
        }
        mock_confirm.return_value = True
        mock_send.return_value = (True, None)
        
        result = compose_email()
        assert result is True


class TestComposeErrorHandling:
    """Tests for error handling in composition"""
    
    @patch('src.ui.composer.save_as_draft')
    @patch('src.ui.composer.show_draft_saved')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_keyboard_interrupt(self, mock_prompt_details, mock_show_draft,
                                             mock_save_draft):
        """Test handling keyboard interrupt during composition"""
        mock_prompt_details.side_effect = KeyboardInterrupt()
        
        try:
            result = compose_email()
            # May return False or raise exception
            assert result is False or result is None
        except KeyboardInterrupt:
            pass  # Keyboard interrupt is acceptable
    
    @patch('src.ui.composer.prompt_send_later', return_value=None)
    @patch('src.ui.composer.show_send_failed')
    @patch('src.ui.composer.send_email_now')
    @patch('src.ui.composer.confirm_action')
    @patch('src.ui.composer.show_email_preview')
    @patch('src.ui.composer.prompt_email_details')
    def test_compose_email_send_failure(self, mock_prompt_details, mock_show_preview,
                                       mock_confirm, mock_send, mock_show_failed,
                                       mock_prompt_later):
        """Test handling send failure"""
        mock_prompt_details.return_value = {
            'recipient': 'recipient@example.com',
            'subject': 'Test',
            'body': 'Body'
        }
        mock_confirm.return_value = True
        mock_send.return_value = (False, "SMTP Error")
        
        result = compose_email()
        assert result is False or result is None
