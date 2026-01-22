package protocol

import "encoding/json"

// Request from Python
type Request struct {
    Module string          `json:"module"` // "imap" or "smtp"
    Action string          `json:"action"` // "connect", "fetch", "send", etc.
    Params json.RawMessage `json:"params"`
}

// Response to Python
type Response struct {
    Success bool        `json:"success"`
    Data    any         `json:"data,omitempty"`
    Error   string      `json:"error,omitempty"`
}

// ErrorResponse creates an error response
func ErrorResponse(err error) Response {
    return Response{
        Success: false,
        Error:   err.Error(),
    }
}

// SuccessResponse creates a success response
func SuccessResponse(data any) Response {
    return Response{
        Success: true,
        Data:    data,
    }
}
