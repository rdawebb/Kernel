package smtp

import (
	"crypto/tls"
	"fmt"
	"net"
	"net/smtp"
	"sync"
	"time"
)

// Connection wraps an SMTP client connection
type Connection struct {
    mu          sync.RWMutex
    client      *smtp.Client
    host        string
    port        int
    username    string
    connectedAt time.Time
    closed      bool
}

// Connect establishes an SMTP connection
func Connect(host string, port int, username, password string) (*Connection, error) {
    addr := fmt.Sprintf("[%s]:%d", host, port)
    var conn net.Conn
    var err error

    if port == 465 {
        // Implicit TLS
        conn, err = tls.Dial("tcp", addr, &tls.Config{ServerName: host})
        if err != nil {
            return nil, fmt.Errorf("failed to connect (TLS): %w", err)
        }
    } else {
        // Plain TCP, will upgrade to TLS via STARTTLS
        conn, err = net.Dial("tcp", addr)
        if err != nil {
            return nil, fmt.Errorf("failed to connect: %w", err)
        }
    }

    c, err := smtp.NewClient(conn, host)
    if err != nil {
        return nil, fmt.Errorf("failed to create SMTP client: %w", err)
    }

    // Upgrade to TLS if not already using it
    if port != 465 {
        if ok, _ := c.Extension("STARTTLS"); ok {
            if err = c.StartTLS(&tls.Config{ServerName: host}); err != nil {
                c.Quit()
                return nil, fmt.Errorf("STARTTLS failed: %w", err)
            }
        }
    }

    // Authenticate
    auth := smtp.PlainAuth("", username, password, host)
    if err = c.Auth(auth); err != nil {
        c.Quit()
        return nil, fmt.Errorf("authentication failed: %w", err)
    }

    return &Connection{
        client:      c,
        host:        host,
        port:        port,
        username:    username,
        connectedAt: time.Now(),
    }, nil
}

// Close closes the connection
func (c *Connection) Close() error {
    c.mu.Lock()
    defer c.mu.Unlock()

    if c.closed || c.client == nil {
        return nil
    }

    c.closed = true
    err := c.client.Quit()
    c.client = nil
    return err
}

func (c *Connection) IsClosed() bool {
    c.mu.RLock()
    defer c.mu.RUnlock()
    return c.closed
}

// Noop sends a NOOP to keep connection alive
func (c *Connection) Noop() error {
    c.mu.RLock()
    if c.closed || c.client == nil {
        c.mu.RUnlock()
        return fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.RUnlock()
    return client.Noop()
}

// GetClient returns the underlying SMTP client
func (c *Connection) GetClient() *smtp.Client {
    return c.client
}
