from fastapi import WebSocket
from typing import Dict, List, Any
import json
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, List[str]] = {}  # event_type -> [client_ids]
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            # Remove from all subscriptions
            for event_type in self.subscriptions:
                if client_id in self.subscriptions[event_type]:
                    self.subscriptions[event_type].remove(client_id)
            print(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")
    
    def subscribe(self, client_id: str, event_type: str):
        """Subscribe a client to an event type."""
        if event_type not in self.subscriptions:
            self.subscriptions[event_type] = []
        if client_id not in self.subscriptions[event_type]:
            self.subscriptions[event_type].append(client_id)
    
    def unsubscribe(self, client_id: str, event_type: str):
        """Unsubscribe a client from an event type."""
        if event_type in self.subscriptions and client_id in self.subscriptions[event_type]:
            self.subscriptions[event_type].remove(client_id)
    
    async def send_personal_message(self, client_id: str, message: Dict[str, Any]):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                print(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: Dict[str, Any], event_type: str = None):
        """Broadcast a message to all connected clients or subscribers of an event type."""
        if event_type and event_type in self.subscriptions:
            # Send to subscribers only
            client_ids = self.subscriptions[event_type].copy()
        else:
            # Send to all clients
            client_ids = list(self.active_connections.keys())
        
        disconnected = []
        for client_id in client_ids:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception as e:
                    print(f"Error broadcasting to {client_id}: {e}")
                    disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)
    
    async def emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emit an event to all subscribers."""
        message = {
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message, event_type)
    
    # Event-specific methods
    async def emit_ticket_created(self, ticket_data: Dict[str, Any]):
        """Emit ticket:created event."""
        await self.emit_event("ticket:created", ticket_data)
    
    async def emit_ticket_updated(self, ticket_id: str, updates: Dict[str, Any]):
        """Emit ticket:updated event."""
        await self.emit_event("ticket:updated", {
            "ticket_id": ticket_id,
            "updates": updates
        })
    
    async def emit_ticket_assigned(self, ticket_id: str, assigned_team: str):
        """Emit ticket:assigned event."""
        await self.emit_event("ticket:assigned", {
            "ticket_id": ticket_id,
            "assigned_team": assigned_team,
        })
    
    async def emit_ticket_resolved(self, ticket_id: str, resolution: Dict[str, Any]):
        """Emit ticket:resolved event."""
        await self.emit_event("ticket:resolved", {
            "ticket_id": ticket_id,
            "resolution": resolution
        })
    
    async def emit_insight_generated(self, ticket_id: str, insights: Dict[str, Any]):
        """Emit insight:generated event."""
        await self.emit_event("insight:generated", {
            "ticket_id": ticket_id,
            "insights": insights
        })
    
    async def emit_solution_suggested(self, ticket_id: str, solution: Dict[str, Any]):
        """Emit solution:suggested event."""
        await self.emit_event("solution:suggested", {
            "ticket_id": ticket_id,
            "solution": solution
        })
    
    async def emit_triage_stats_updated(self, stats: List[Dict[str, Any]]):
        """Emit triage:stats_updated event."""
        await self.emit_event("triage:stats_updated", {
            "stats": stats
        })

    async def emit_reply_sent(self, ticket_id: str, message: Dict[str, Any]):
        """Emit ticket:reply_sent event."""
        await self.emit_event("ticket:reply_sent", {
            "ticket_id": ticket_id,
            "message": message
        })
    
    async def emit_customer_message(self, ticket_id: str, message: Dict[str, Any]):
        """Emit customer:message event (customer sent a message)."""
        await self.emit_event("customer:message", {
            "ticket_id": ticket_id,
            "message": message
        })
    
    async def emit_agent_message(self, ticket_id: str, message: Dict[str, Any]):
        """Emit agent:message event (agent sent a reply)."""
        await self.emit_event("agent:message", {
            "ticket_id": ticket_id,
            "message": message
        })
    
    async def emit_customer_typing(self, ticket_id: str, customer_name: str):
        """Emit customer:typing event."""
        await self.emit_event("customer:typing", {
            "ticket_id": ticket_id,
            "customer_name": customer_name
        })
    
    async def emit_agent_typing(self, ticket_id: str, agent_name: str):
        """Emit agent:typing event."""
        await self.emit_event("agent:typing", {
            "ticket_id": ticket_id,
            "agent_name": agent_name
        })

# Global connection manager instance
manager = ConnectionManager()
