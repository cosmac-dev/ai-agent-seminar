#!/usr/bin/env bash

# A script to automate the execution of the a2a_mcp example.
# It starts all necessary servers and agents in the background.
# By default it runs the MCP test client and exits. With --serve it keeps the
# services running for Notebook and LangGraph Studio demonstrations.

# Exit immediately if a command exits with a non-zero status.
set -Eeuo pipefail

# --- Configuration ---
WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Directory to store log files for background processes
LOG_DIR="${TMPDIR:-/tmp}/a2a-mcp-logs"
MODE="${1:-client}"
if [[ "$MODE" != "client" && "$MODE" != "--serve" ]]; then
    echo "Usage: $0 [--serve]"
    exit 2
fi

# Array to store Process IDs (PIDs) of background jobs.
pids=()


# --- Cleanup Function ---
# This function is called automatically when the script exits (for any reason)
# to ensure all background processes are terminated.
cleanup() {
    echo ""
    echo "Shutting down background processes..."
    # Check if the pids array is not empty
    if [[ ${#pids[@]} -ne 0 ]]; then
        # Kill all processes using their PIDs stored in the array.
        # The 2>/dev/null suppresses "Terminated" messages or errors if a process is already gone.
        kill "${pids[@]}" 2>/dev/null || true
        wait "${pids[@]}" 2>/dev/null || true
    fi
    echo "Cleanup complete."
}

# Trap the EXIT signal to call the cleanup function. This ensures cleanup
# runs whether the script finishes successfully, fails, or is interrupted.
trap cleanup EXIT


# --- Main Script Logic ---

# Navigate into the working directory.
cd "$WORK_DIR"
echo "Changed directory to $(pwd)"

# Create a directory for log files if it doesn't exist.
mkdir -p "$LOG_DIR"

echo "Synchronizing Python dependencies with 'uv'..."
uv sync --locked

port_is_open() {
    (exec 3<>"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
}

for port in {10100..10105}; do
    if port_is_open "$port"; then
        echo "Error: Port $port is already in use."
        echo "Stop the existing service and run this script again."
        exit 1
    fi
done

wait_for_service() {
    local name="$1"
    local port="$2"
    local pid="$3"
    local log_file="$4"

    for _ in {1..180}; do
        if port_is_open "$port"; then
            echo "-> $name is ready on port $port"
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "Error: $name stopped before becoming ready."
            echo "See $log_file"
            return 1
        fi
        sleep 1
    done

    echo "Error: Timed out waiting for $name on port $port."
    echo "See $log_file"
    return 1
}

# --- Start Background Services ---
echo ""
echo "Starting servers and agents in the background..."

# 1. Start MCP Server
echo "-> Starting MCP Server (Port: 10100)... Log: $LOG_DIR/mcp_server.log"
uv run a2a-mcp --run mcp-server --transport sse --port 10100 > "$LOG_DIR/mcp_server.log" 2>&1 &
pids+=($!)

# 2. Start Orchestrator Agent
echo "-> Starting Orchestrator Agent (Port: 10101)... Log: $LOG_DIR/orchestrator_agent.log"
uv run src/a2a_mcp/agents/ --agent-card agent_cards/orchestrator_agent.json --port 10101 > "$LOG_DIR/orchestrator_agent.log" 2>&1 &
pids+=($!)

# 3. Start Planner Agent
echo "-> Starting Planner Agent (Port: 10102)... Log: $LOG_DIR/planner_agent.log"
uv run src/a2a_mcp/agents/ --agent-card agent_cards/planner_agent.json --port 10102 > "$LOG_DIR/planner_agent.log" 2>&1 &
pids+=($!)

# 4. Start Airline Ticketing Agent
echo "-> Starting Airline Agent (Port: 10103)... Log: $LOG_DIR/airline_agent.log"
uv run src/a2a_mcp/agents/ --agent-card agent_cards/air_ticketing_agent.json --port 10103 > "$LOG_DIR/airline_agent.log" 2>&1 &
pids+=($!)

# 5. Start Hotel Reservations Agent
echo "-> Starting Hotel Agent (Port: 10104)... Log: $LOG_DIR/hotel_agent.log"
uv run src/a2a_mcp/agents/ --agent-card agent_cards/hotel_booking_agent.json --port 10104 > "$LOG_DIR/hotel_agent.log" 2>&1 &
pids+=($!)

# 6. Start Car Rental Reservations Agent
echo "-> Starting Car Rental Agent (Port: 10105)... Log: $LOG_DIR/car_rental_agent.log"
uv run src/a2a_mcp/agents/ --agent-card agent_cards/car_rental_agent.json --port 10105 > "$LOG_DIR/car_rental_agent.log" 2>&1 &
pids+=($!)

echo ""
echo "Waiting for services to become ready..."
wait_for_service "MCP Server" 10100 "${pids[0]}" "$LOG_DIR/mcp_server.log"
wait_for_service "Orchestrator Agent" 10101 "${pids[1]}" "$LOG_DIR/orchestrator_agent.log"
wait_for_service "Planner Agent" 10102 "${pids[2]}" "$LOG_DIR/planner_agent.log"
wait_for_service "Airline Agent" 10103 "${pids[3]}" "$LOG_DIR/airline_agent.log"
wait_for_service "Hotel Agent" 10104 "${pids[4]}" "$LOG_DIR/hotel_agent.log"
wait_for_service "Car Rental Agent" 10105 "${pids[5]}" "$LOG_DIR/car_rental_agent.log"

if [[ "$MODE" == "--serve" ]]; then
    echo ""
    echo "All A2A services are ready."
    echo "Use Notebook now, or run 'uv run langgraph dev --no-browser' in another terminal for Studio."
    echo "Press Ctrl+C to stop the services."
    set +e
    wait -n "${pids[@]}"
    status=$?
    set -e
    echo "A background service stopped."
    exit "$status"
fi

# --- Run the Foreground Client ---
echo ""
echo "---------------------------------------------------------"
echo "Starting CLI Client..."
echo "The script will exit after the client finishes."
echo "---------------------------------------------------------"
echo ""

# 7. Start the CLI client in the foreground.
# The script will pause here until this command completes.
uv run src/a2a_mcp/mcp/client.py --transport sse --resource "resource://agent_cards/list" --find_agent "I would like to plan a trip to France."

echo ""
echo "---------------------------------------------------------"
echo "CLI client finished."
echo "---------------------------------------------------------"

# The 'trap' will now trigger the 'cleanup' function automatically upon exiting.
