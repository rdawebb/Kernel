package smtp

import (
	"fmt"
)

// SendMessage sends an email message
func (c *Connection) SendMessage(from string, to []string, message []byte) error {
    c.mu.RLock()
    if c.closed || c.client == nil {
        c.mu.RUnlock()
        return fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.RUnlock()

    // Set sender
    if err := client.Mail(from); err != nil {
        return fmt.Errorf("MAIL FROM failed: %w", err)
    }

    // Set recipients
    for _, recipient := range to {
        if err := client.Rcpt(recipient); err != nil {
            return fmt.Errorf("RCPT TO failed for %s: %w", recipient, err)
        }
    }

    // Send message data
    w, err := client.Data()
    if err != nil {
        return fmt.Errorf("DATA command failed: %w", err)
    }
    defer w.Close()

    if _, err := w.Write(message); err != nil {
        return fmt.Errorf("failed to write message: %w", err)
    }

    if err := w.Close(); err != nil {
        return fmt.Errorf("failed to close DATA: %w", err)
    }

    return nil
}
