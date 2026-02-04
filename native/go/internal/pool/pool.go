package pool

import (
	"errors"
	"fmt"
	"sync"
)

type ConnectionPool struct {
    mu          sync.RWMutex
    connections map[int]any
    nextID      uint64
}

func NewConnectionPool() *ConnectionPool {
    return &ConnectionPool{
        connections: make(map[int]any),
        nextID:      1,
    }
}

func (p *ConnectionPool) Add(conn any) (int, error) {
    p.mu.Lock()
    defer p.mu.Unlock()

    if len(p.connections) >= 10000 {
        return 0, fmt.Errorf("connection pool limit reached")
    }

    handle := int(p.nextID)
    p.nextID++
    p.connections[handle] = conn

    return handle, nil
}

func (p *ConnectionPool) Get(handle int) (any, error) {
    p.mu.RLock()
    defer p.mu.RUnlock()

    conn, ok := p.connections[handle]
    if !ok {
        return nil, errors.New("invalid connection handle")
    }

    return conn, nil
}

func (p *ConnectionPool) Remove(handle int) {
    p.mu.Lock()
    defer p.mu.Unlock()

    delete(p.connections, handle)
}

func (p *ConnectionPool) Count() int {
    p.mu.RLock()
    defer p.mu.RUnlock()

    return len(p.connections)
}
