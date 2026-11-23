# ==========================================
# Build Stage (Go 1.24 Multi-stage)
# ==========================================
FROM golang:1.24-alpine AS builder

WORKDIR /build

# Install git and ca-certificates
RUN apk add --no-cache git ca-certificates tzdata

# Cache dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY cmd/ ./cmd/
COPY internal/ ./internal/

# Build statically linked binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-s -w -X main.version=1.0.0" \
    -o /build/da-setex-collector \
    ./cmd/collector

# ==========================================
# Production Runtime Stage (Minimal Alpine)
# ==========================================
FROM alpine:3.20

WORKDIR /app

# Install timezone data & certificates
RUN apk add --no-cache tzdata ca-certificates && \
    cp /usr/share/zoneinfo/Asia/Jakarta /etc/localtime && \
    echo "Asia/Jakarta" > /etc/timezone

# Create non-root user for security
RUN adduser -D -u 1000 da-collector && \
    chown -R da-collector:da-collector /app

# Copy compiled binary from builder
COPY --from=builder /build/da-setex-collector /app/da-setex-collector

USER da-collector

# Healthcheck probe (process running)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD pidof da-setex-collector || exit 1

ENTRYPOINT ["/app/da-setex-collector"]
CMD ["/app/config.yaml"]
