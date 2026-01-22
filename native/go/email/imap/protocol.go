package imap

import (
	"encoding/base64"
	"fmt"
	"io"

	"github.com/emersion/go-imap"
)

// SelectFolder selects an IMAP folder
func (c *Connection) SelectFolder(folder string) error {
    c.mu.RLock()
    if c.closed || c.client == nil {
        c.mu.RUnlock()
        return fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.RUnlock()

    _, err := client.Select(folder, false)
    return err
}

// SearchUIDs searches for message UIDs
func (c *Connection) SearchUIDs(highestUID uint32) ([]uint32, error) {
    c.mu.RLock()
    if c.closed || c.client == nil {
        c.mu.RUnlock()
        return nil, fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.RUnlock()

    // Parse criteria, all if no highestUID
    searchCriteria := imap.NewSearchCriteria()
    if highestUID > 0 {
        searchCriteria.Uid = new(imap.SeqSet)
        searchCriteria.Uid.AddRange(highestUID+1, 0)
    } else {
        searchCriteria.Uid = new(imap.SeqSet)
        searchCriteria.Uid.AddRange(1, 0)
    }

    uids, err := client.UidSearch(searchCriteria)
    if err != nil {
        return nil, fmt.Errorf("search failed: %w", err)
    }

    return uids, nil
}

// FetchMessage fetches a single message by UID
func (c *Connection) FetchMessage(uid uint32) ([]byte, error) {
    c.mu.RLock()
    if c.closed || c.client == nil {
        c.mu.RUnlock()
        return nil, fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.RUnlock()

    seqSet := new(imap.SeqSet)
    seqSet.AddNum(uid)

    messages := make(chan *imap.Message, 1)
    done := make(chan error, 1)

    go func() {
        done <- client.UidFetch(seqSet, []imap.FetchItem{imap.FetchRFC822}, messages)
    }()

    msg := <-messages
    if msg == nil {
        return nil, fmt.Errorf("message not found")
    }

    if err := <-done; err != nil {
        return nil, fmt.Errorf("fetch failed: %w", err)
    }

    literal := msg.GetBody(&imap.BodySectionName{})
    if literal == nil {
        return nil, fmt.Errorf("no message body")
    }

    body, err := io.ReadAll(literal)
    if err != nil {
        return nil, fmt.Errorf("failed to read body: %w", err)
    }

    return body, nil
}

// FetchMessages fetches multiple messages by UID
func (c *Connection) FetchMessages(uids []uint32) (map[uint32]string, error) {
    c.mu.RLock()
    if c.closed || c.client == nil {
        c.mu.RUnlock()
        return nil, fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.RUnlock()

    if len(uids) == 0 {
        return make(map[uint32]string), nil
    }

    seqSet := new(imap.SeqSet)
    for _, uid := range uids {
        seqSet.AddNum(uid)
    }

    messages := make(chan *imap.Message, len(uids))
    done := make(chan error, 1)

    go func() {
        done <- client.UidFetch(seqSet, []imap.FetchItem{imap.FetchRFC822}, messages)
    }()

    result := make(map[uint32]string)

    for msg := range messages {
        if msg == nil {
            continue
        }

        literal := msg.GetBody(&imap.BodySectionName{})
        if literal == nil {
            continue
        }

        body, err := io.ReadAll(literal)
        if err != nil {
            continue
        }

        // Encode as base64 for JSON transport
        result[msg.Uid] = base64.StdEncoding.EncodeToString(body)
    }

    if err := <-done; err != nil {
        return nil, fmt.Errorf("fetch failed: %w", err)
    }

    return result, nil
}

// SetFlags sets flags on a message
func (c *Connection) SetFlags(uid uint32, flags []string, add bool) error {
    c.mu.Lock()
    if c.closed || c.client == nil {
        c.mu.Unlock()
        return fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.Unlock()

    seqSet := new(imap.SeqSet)
    seqSet.AddNum(uid)

    var operation imap.FlagsOp
    if add {
        operation = imap.AddFlags
    } else {
        operation = imap.RemoveFlags
    }

    item := imap.FormatFlagsOp(operation, false)
    return client.UidStore(seqSet, item, flags, nil)
}

// CopyMessage copies a message to another folder
func (c *Connection) CopyMessage(uid uint32, destFolder string) error {
    c.mu.Lock()
    if c.closed || c.client == nil {
        c.mu.Unlock()
        return fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.Unlock()

    seqSet := new(imap.SeqSet)
    seqSet.AddNum(uid)

    return client.UidCopy(seqSet, destFolder)
}

// Expunge permanently removes deleted messages
func (c *Connection) Expunge() error {
    c.mu.Lock()
    if c.closed || c.client == nil {
        c.mu.Unlock()
        return fmt.Errorf("client not connected")
    }
    client := c.client
    c.mu.Unlock()

    return client.Expunge(nil)
}
