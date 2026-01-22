package smtp

import (
	"encoding/base64"
	"encoding/json"
	"fmt"

	"github.com/rdawebb/kernel/native/internal/pool"
	"github.com/rdawebb/kernel/native/internal/protocol"
)

// Handler handles SMTP requests from Python
type Handler struct {
    pool *pool.ConnectionPool
}

// NewHandler creates a new SMTP handler
func NewHandler() *Handler {
    return &Handler{
        pool: pool.NewConnectionPool(),
    }
}

// Handle processes an SMTP request
func (h *Handler) Handle(req protocol.Request) protocol.Response {
    switch req.Action {
    case "connect":
        return h.handleConnect(req.Params)
    case "close":
        return h.handleClose(req.Params)
    case "send":
        return h.handleSend(req.Params)
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

func (h *Handler) handleSend(params json.RawMessage) protocol.Response {
    var p struct {
        Handle     int      `json:"handle"`
        From       string   `json:"from"`
        To         []string `json:"to"`
        MessageB64 string   `json:"message_b64"`
    }

    if err := json.Unmarshal(params, &p); err != nil {
        return protocol.ErrorResponse(err)
    }

    connInterface, err := h.pool.Get(p.Handle)
    if err != nil {
        return protocol.ErrorResponse(err)
    }

    // Decode base64 message
    message, err := base64.StdEncoding.DecodeString(p.MessageB64)
    if err != nil {
        return protocol.ErrorResponse(fmt.Errorf("invalid base64 message: %w", err))
    }

    conn := connInterface.(*Connection)
    if err := conn.SendMessage(p.From, p.To, message); err != nil {
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
