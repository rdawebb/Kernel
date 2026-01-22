package imap

import (
	"crypto/tls"
	"fmt"
	"sync"
	"time"

	"github.com/emersion/go-imap/client"
)

// Connection wraps an IMAP client connection
type Connection struct {
    mu          sync.RWMutex
    client      *client.Client
    host        string
    port        int
    username    string
    connectedAt time.Time
    closed      bool
}

// Connect establishes an IMAP connection
func Connect(host string, port int, username, password string) (*Connection, error) {
    addr := fmt.Sprintf("%s:%d", host, port)
    
    // Connect with TLS
    c, err := client.DialTLS(addr, &tls.Config{
        ServerName: host,
    })
    if err != nil {
        return nil, fmt.Errorf("failed to connect: %w", err)
    }

    // Login
    if err := c.Login(username, password); err != nil {
        c.Logout()
        return nil, fmt.Errorf("login failed: %w", err)
    }

    return &Connection{
        mu:          sync.RWMutex{},
        client:      c,
        host:        host,
        port:        port,
        username:    username,
        connectedAt: time.Now(),
        closed:      false,
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
    err := c.client.Logout()
    c.client = nil
    return err
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

// GetClient returns the underlying IMAP client
func (c *Connection) GetClient() *client.Client {
    return c.client
}
