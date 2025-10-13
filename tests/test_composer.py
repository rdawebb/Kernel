from unittest.mock import patch, call
from email_validator import EmailNotValidError
from src.tui_mail.ui.composer import compose_email


class TestComposeEmail:
    """Test the interactive email composer"""
    
    @patch('src.tui_mail.ui.composer.save_sent_email')
    @patch('src.tui_mail.ui.composer.send_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_success(self, mock_console, mock_validate, mock_confirm, mock_send, mock_save_sent):
        """Test successful email composition and sending"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'  # valid email
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            'Test Subject',      # subject
            'Line 1',           # body line 1
            'Line 2',           # body line 2
            '',                 # empty line
            '',                 # second empty line to finish
            ''                  # send time (empty = immediate)
        ]
        mock_confirm.return_value = True  # confirm send
        mock_send.return_value = True     # send succeeds
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is True
        mock_send.assert_called_once_with(
            to_email='test@example.com',
            subject='Test Subject',
            body='Line 1\nLine 2'
        )
        mock_confirm.assert_called_once_with("\nSend this email?")
        mock_save_sent.assert_called_once()
    
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_empty_recipient(self, mock_console):
        """Test composer with empty recipient"""
        # Setup
        mock_console.input.return_value = ''  # empty recipient
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        mock_console.print.assert_called_with("[bold red]Recipient email is required.[/bold red]")
    
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_whitespace_recipient(self, mock_console):
        """Test composer with whitespace-only recipient"""
        # Setup
        mock_console.input.return_value = '   '  # whitespace recipient
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        mock_console.print.assert_called_with("[bold red]Recipient email is required.[/bold red]")
    
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_invalid_email(self, mock_console, mock_validate):
        """Test composer with invalid email address"""
        # Setup
        mock_console.input.return_value = 'invalid-email'
        mock_validate.side_effect = EmailNotValidError("Invalid email")
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        mock_console.print.assert_called_with("[bold red]Invalid email address: Invalid email[/bold red]")
    
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_empty_subject_cancel(self, mock_console, mock_confirm, mock_validate):
        """Test composer with empty subject and user cancels"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            '',                  # empty subject
        ]
        mock_confirm.return_value = False  # don't continue with empty subject
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        mock_confirm.assert_called_once_with("Subject is empty, continue anyway?")
    
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_empty_subject_continue(self, mock_console, mock_confirm, mock_validate):
        """Test composer with empty subject and user continues"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            '',                  # empty subject
            'Some body text',    # body
            '',                  # empty line
            ''                   # second empty line to finish
        ]
        mock_confirm.side_effect = [True, False]  # continue with empty subject, don't send
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        calls = [call("Subject is empty, continue anyway?"), call("\nSend this email?")]
        mock_confirm.assert_has_calls(calls)
    
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_empty_body_cancel(self, mock_console, mock_confirm, mock_validate):
        """Test composer with empty body and user cancels"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            'Test Subject',      # subject
            '',                  # empty body line
            ''                   # second empty line to finish
        ]
        mock_confirm.return_value = False  # don't continue with empty body
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        mock_confirm.assert_called_once_with("Body is empty, continue anyway?")
    
    @patch('src.tui_mail.ui.composer.save_sent_email')
    @patch('src.tui_mail.ui.composer.send_email')
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_empty_body_continue(self, mock_console, mock_confirm, mock_validate, mock_send, mock_save_sent):
        """Test composer with empty body and user continues"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            'Test Subject',      # subject
            '',                  # empty body line
            '',                  # second empty line to finish
            ''                   # send time (empty = immediate)
        ]
        mock_confirm.side_effect = [True, True]  # continue with empty body, send
        mock_send.return_value = True
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is True
        calls = [call("Body is empty, continue anyway?"), call("\nSend this email?")]
        mock_confirm.assert_has_calls(calls)
        mock_send.assert_called_once_with(
            to_email='test@example.com',
            subject='Test Subject',
            body=''
        )
    
    @patch('src.tui_mail.ui.composer.save_draft_email')
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_user_cancels_send(self, mock_console, mock_confirm, mock_validate, mock_save_draft):
        """Test composer when user cancels at final confirmation"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            'Test Subject',      # subject
            'Test body',         # body
            '',                  # empty line
            ''                   # second empty line to finish
        ]
        mock_confirm.return_value = False  # don't send
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        mock_confirm.assert_called_once_with("\nSend this email?")
        mock_console.print.assert_called_with("[yellow]Email cancelled - saved as draft.[/yellow]")
        mock_save_draft.assert_called_once()
    
    @patch('src.tui_mail.ui.composer.save_sent_email')
    @patch('src.tui_mail.ui.composer.send_email')
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_send_failure(self, mock_console, mock_confirm, mock_validate, mock_send, mock_save_sent):
        """Test composer when email sending fails"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            'Test Subject',      # subject
            'Test body',         # body
            '',                  # empty line
            '',                  # second empty line to finish
            ''                   # send time (empty = immediate)
        ]
        mock_confirm.return_value = True  # confirm send
        mock_send.return_value = False    # send fails
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        mock_console.print.assert_called_with("[bold red]Failed to send email - will try again later.[/bold red]")
        mock_save_sent.assert_called_once()
    
    @patch('src.tui_mail.ui.composer.save_sent_email')
    @patch('src.tui_mail.ui.composer.send_email')
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_send_exception(self, mock_console, mock_confirm, mock_validate, mock_send, mock_save_sent):
        """Test composer when email sending raises exception"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            'Test Subject',      # subject
            'Test body',         # body
            '',                  # empty line
            '',                  # second empty line to finish
            ''                   # send time (empty = immediate)
        ]
        mock_confirm.return_value = True  # confirm send
        mock_send.side_effect = RuntimeError("SMTP error")
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is False
        mock_console.print.assert_called_with("[bold red]Error sending email: SMTP error - will try again later.[/bold red]")
        mock_save_sent.assert_called_once()
    
    @patch('src.tui_mail.ui.composer.save_sent_email')
    @patch('src.tui_mail.ui.composer.send_email')
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.confirm_action')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_multiline_body(self, mock_console, mock_confirm, mock_validate, mock_send, mock_save_sent):
        """Test composer with multi-line body"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            'Test Subject',      # subject
            'First line',        # body line 1
            'Second line',       # body line 2
            '',                  # empty line
            'Third line',        # body line 3
            '',                  # empty line
            '',                  # second consecutive empty line to finish
            ''                   # send time (empty = immediate)
        ]
        mock_confirm.return_value = True
        mock_send.return_value = True
        
        # Test
        result = compose_email()
        
        # Verify
        assert result is True
        expected_body = 'First line\nSecond line\n\nThird line'
        mock_send.assert_called_once_with(
            to_email='test@example.com',
            subject='Test Subject',
            body=expected_body
        )
    
    @patch('src.tui_mail.ui.composer.validate_email')
    @patch('src.tui_mail.ui.composer.console')
    def test_compose_email_displays_preview(self, mock_console, mock_validate):
        """Test that email preview is displayed correctly"""
        # Setup
        mock_validate.return_value.email = 'test@example.com'
        mock_console.input.side_effect = [
            'test@example.com',  # recipient
            'Test Subject',      # subject
            'Test body',         # body
            '',                  # empty line
            ''                   # second empty line to finish
        ]
        
        with patch('src.tui_mail.ui.composer.confirm_action', return_value=False):
            # Test
            compose_email()
        
        # Verify preview is displayed
        preview_calls = [call for call in mock_console.print.call_args_list 
                        if 'Email Preview' in str(call)]
        assert len(preview_calls) > 0
        
        # Check preview content calls
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        preview_content = '\n'.join(print_calls)
        assert 'test@example.com' in preview_content
        assert 'Test Subject' in preview_content
        assert 'Test body' in preview_content