package imap

import (
	"encoding/json"
	"fmt"

	"github.com/rdawebb/kernel/native/internal/pool"
	"github.com/rdawebb/kernel/native/internal/protocol"
)

// Handler handles IMAP requests from Python
type Handler struct {
    pool *pool.ConnectionPool
}

// NewHandler creates a new IMAP handler
func NewHandler() *Handler {
    return &Handler{
        pool: pool.NewConnectionPool(),
    }
}

// Handle processes an IMAP request
func (h *Handler) Handle(req protocol.Request) protocol.Response {
    switch req.Action {
    case "connect":
        return h.handleConnect(req.Params)
    case "close":
        return h.handleClose(req.Params)
    case "select_folder":
        return h.handleSelectFolder(req.Params)
    case "search_uids":
        return h.handleSearchUIDs(req.Params)
    case "fetch_messages":
        return h.handleFetchMessages(req.Params)
    case "set_flags":
        return h.handleSetFlags(req.Params)
    case "copy_message":
        return h.handleCopyMessage(req.Params)
    case "expunge":
        return h.handleExpunge(req.Params)
    case "noop":
        return h.handleNoop(req.Params)
    default:
        return protocol.ErrorResponse(fmt.Errorf("unknown action: %s", req.Action))
    }
}

func (h *Handler) handleConnect(params json.RawMessage) protocol.Response {
    var p struct {
        Host     string `json:"host"`
        Port     int    `json:"port"`
        Username string `json:"username"`
        Password string `json:"password"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    conn, err := Connect(p.Host, p.Port, p.Username, p.Password)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    handle, err := h.pool.Add(conn)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    return protocol.SuccessResponse(map[string]any{
        "handle": handle,
    })
}

func (h *Handler) handleClose(params json.RawMessage) protocol.Response {
    var p struct {
        Handle int `json:"handle"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    conn := connInterface.(*Connection)
    if err := conn.Close(); err != nil {
        return protocol.ErrorResponse(err)
    }

    h.pool.Remove(p.Handle)
    return protocol.SuccessResponse(nil)
}

func (h *Handler) handleSelectFolder(params json.RawMessage) protocol.Response {
    var p struct {
        Handle int    `json:"handle"`
        Folder string `json:"folder"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    conn := connInterface.(*Connection)
    if err := conn.SelectFolder(p.Folder); err != nil {
        return protocol.ErrorResponse(err)
    }

    return protocol.SuccessResponse(nil)
}

func (h *Handler) handleSearchUIDs(params json.RawMessage) protocol.Response {
    var p struct {
        Handle    int    `json:"handle"`
        HighestUID uint32 `json:"highest_uid"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    conn := connInterface.(*Connection)
    uids, err := conn.SearchUIDs(p.HighestUID)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    return protocol.SuccessResponse(map[string]any{
        "uids": uids,
    })
}

func (h *Handler) handleFetchMessages(params json.RawMessage) protocol.Response {
    var p struct {
        Handle int      `json:"handle"`
        UIDs   []uint32 `json:"uids"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    conn := connInterface.(*Connection)
    messages, err := conn.FetchMessages(p.UIDs)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    return protocol.SuccessResponse(map[string]any{
        "messages": messages,
    })
}

func (h *Handler) handleSetFlags(params json.RawMessage) protocol.Response {
    var p struct {
        Handle int      `json:"handle"`
        UID    uint32   `json:"uid"`
        Flags  []string `json:"flags"`
        Add    bool     `json:"add"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    conn := connInterface.(*Connection)
    if err := conn.SetFlags(p.UID, p.Flags, p.Add); err != nil {
        return protocol.ErrorResponse(err)
    }

    return protocol.SuccessResponse(nil)
}

func (h *Handler) handleCopyMessage(params json.RawMessage) protocol.Response {
    var p struct {
        Handle     int    `json:"handle"`
        UID        uint32 `json:"uid"`
        DestFolder string `json:"dest_folder"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    conn := connInterface.(*Connection)
    if err := conn.CopyMessage(p.UID, p.DestFolder); err != nil {
        return protocol.ErrorResponse(err)
    }

    return protocol.SuccessResponse(nil)
}

func (h *Handler) handleExpunge(params json.RawMessage) protocol.Response {
    var p struct {
        Handle int `json:"handle"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    conn := connInterface.(*Connection)
    if err := conn.Expunge(); err != nil {
        return protocol.ErrorResponse(err)
    }

    return protocol.SuccessResponse(nil)
}

func (h *Handler) handleNoop(params json.RawMessage) protocol.Response {
    var p struct {
        Handle int `json:"handle"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    conn := connInterface.(*Connection)
    if err := conn.Noop(); err != nil {
        return protocol.ErrorResponse(err)
    }

    return protocol.SuccessResponse(nil)
}
