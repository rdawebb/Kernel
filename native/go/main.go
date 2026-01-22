package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/rdawebb/kernel/native/email/imap"
	"github.com/rdawebb/kernel/native/email/smtp"
	"github.com/rdawebb/kernel/native/internal/protocol"
)

func main() {
    socketPath := os.Getenv("NATIVE_SOCKET_PATH")
    if socketPath == "" {
        socketPath = "/tmp/email-app.sock"
    }

    // Remove existing socket if it exists
    os.Remove(socketPath)

    listener, err := net.Listen("unix", socketPath)
    if err != nil {
        log.Fatalf("Failed to create socket: %v", err)
    }
    defer os.Remove(socketPath)
    defer listener.Close()

    log.Printf("Native server listening on %s", socketPath)

    // Setup signal handling
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()

    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

    // Initialise handlers
    imapHandler := imap.NewHandler()
    smtpHandler := smtp.NewHandler()

    go func() {
        sig := <-sigChan
        log.Printf("Received signal: %v", sig)
        log.Println("Shutting down...")

        // Close connections

        cancel()
        listener.Close()
    }()

    // Accept connections
    for {
        conn, err := listener.Accept()
        if err != nil {
            select {
            case <-ctx.Done():
                return
            default:
                log.Printf("Accept error: %v", err)
                continue
            }
        }

        go handleConnection(ctx, conn, imapHandler, smtpHandler)
    }
}

func handleConnection(
    ctx context.Context,
    conn net.Conn,
    imapHandler *imap.Handler,
    smtpHandler *smtp.Handler,
) {
    defer conn.Close()

    scanner := bufio.NewScanner(conn)
    encoder := json.NewEncoder(conn)

    for scanner.Scan() {
        select {
        case <-ctx.Done():
            return
        default:
        }

        var req protocol.Request
        if err := json.Unmarshal(scanner.Bytes(), &req); err != nil {
            log.Printf("Invalid request: %v", err)
            encoder.Encode(protocol.ErrorResponse(err))
            continue
        }

        var resp protocol.Response

        switch req.Module {
        case "imap":
            resp = imapHandler.Handle(req)
        case "smtp":
            resp = smtpHandler.Handle(req)
        default:
            resp = protocol.ErrorResponse(fmt.Errorf("unknown module: %s", req.Module))
        }

        if err := encoder.Encode(resp); err != nil {
            log.Printf("Failed to send response: %v", err)
            return
        }
    }

    if err := scanner.Err(); err != nil {
        log.Printf("Scanner error: %v", err)
    }
}
