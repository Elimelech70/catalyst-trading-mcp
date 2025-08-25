"""
Basic MCP (Model Context Protocol) Implementation
For Catalyst Trading System v3.1.0
Created as a placeholder until official MCP is available
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ResourceParams:
    """Parameters for MCP resource requests"""
    uri: str
    params: Dict[str, Any] = None

@dataclass
class ToolParams:
    """Parameters for MCP tool invocations"""
    tool: str
    arguments: Dict[str, Any] = None

@dataclass
class MCPRequest:
    """MCP Request structure"""
    id: str
    method: str
    params: Dict[str, Any]
    
    def to_dict(self):
        return {
            "id": self.id,
            "method": self.method,
            "params": self.params
        }

@dataclass
class MCPResponse:
    """MCP Response structure"""
    id: str
    result: Any = None
    error: Dict[str, Any] = None
    
    def to_dict(self):
        response = {"id": self.id}
        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response

class MCPServer:
    """Basic MCP Server implementation"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.resources = {}
        self.tools = {}
        self.transport = None
        self._running = False
        
    def add_resource(self, uri: str, handler: Callable):
        """Register a resource handler"""
        self.resources[uri] = handler
        logger.info(f"Registered resource: {uri}")
        
    def add_tool(self, name: str, handler: Callable):
        """Register a tool handler"""
        self.tools[name] = handler
        logger.info(f"Registered tool: {name}")
        
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Process incoming MCP requests"""
        try:
            if request.method == "resources/list":
                result = {"resources": list(self.resources.keys())}
                return MCPResponse(id=request.id, result=result)
                
            elif request.method == "tools/list":
                result = {"tools": list(self.tools.keys())}
                return MCPResponse(id=request.id, result=result)
                
            elif request.method == "resources/get":
                uri = request.params.get("uri")
                if uri in self.resources:
                    result = await self.resources[uri](request.params)
                    return MCPResponse(id=request.id, result=result)
                else:
                    error = {"code": -32601, "message": f"Resource not found: {uri}"}
                    return MCPResponse(id=request.id, error=error)
                    
            elif request.method == "tools/invoke":
                tool = request.params.get("tool")
                if tool in self.tools:
                    result = await self.tools[tool](request.params.get("arguments", {}))
                    return MCPResponse(id=request.id, result=result)
                else:
                    error = {"code": -32601, "message": f"Tool not found: {tool}"}
                    return MCPResponse(id=request.id, error=error)
                    
            else:
                error = {"code": -32601, "message": f"Method not found: {request.method}"}
                return MCPResponse(id=request.id, error=error)
                
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            error = {"code": -32603, "message": str(e)}
            return MCPResponse(id=request.id, error=error)
    
    async def start(self, transport):
        """Start the MCP server with given transport"""
        self.transport = transport
        self._running = True
        logger.info(f"Starting MCP server: {self.name}")
        await transport.start(self)
        
    async def stop(self):
        """Stop the MCP server"""
        self._running = False
        if self.transport:
            await self.transport.stop()
        logger.info(f"Stopped MCP server: {self.name}")

class WebSocketTransport:
    """WebSocket transport for MCP"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.host = host
        self.port = port
        self.server = None
        self.clients = set()
        
    async def start(self, mcp_server: MCPServer):
        """Start WebSocket server"""
        async def handler(websocket, path):
            self.clients.add(websocket)
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        request = MCPRequest(
                            id=data.get("id"),
                            method=data.get("method"),
                            params=data.get("params", {})
                        )
                        response = await mcp_server.handle_request(request)
                        await websocket.send(json.dumps(response.to_dict()))
                    except json.JSONDecodeError:
                        error_response = {
                            "id": None,
                            "error": {"code": -32700, "message": "Parse error"}
                        }
                        await websocket.send(json.dumps(error_response))
            finally:
                self.clients.remove(websocket)
        
        self.server = await websockets.serve(handler, self.host, self.port)
        logger.info(f"WebSocket MCP server listening on ws://{self.host}:{self.port}")
        
    async def stop(self):
        """Stop WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for websocket in self.clients:
            await websocket.close()

class StdioTransport:
    """Standard I/O transport for MCP"""
    
    def __init__(self):
        self.reader = None
        self.writer = None
        
    async def start(self, mcp_server: MCPServer):
        """Start stdio transport"""
        import sys
        self.reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self.reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        
        logger.info("Stdio MCP transport started")
        
        # Read loop
        while mcp_server._running:
            try:
                line = await self.reader.readline()
                if not line:
                    break
                    
                data = json.loads(line.decode())
                request = MCPRequest(
                    id=data.get("id"),
                    method=data.get("method"),
                    params=data.get("params", {})
                )
                response = await mcp_server.handle_request(request)
                print(json.dumps(response.to_dict()), flush=True)
                
            except json.JSONDecodeError:
                error_response = {
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                logger.error(f"Stdio transport error: {e}")
                
    async def stop(self):
        """Stop stdio transport"""
        pass

# Helper functions for common patterns
def create_resource_handler(data_func):
    """Create a resource handler from a data function"""
    async def handler(params):
        return await data_func(params) if asyncio.iscoroutinefunction(data_func) else data_func(params)
    return handler

def create_tool_handler(action_func):
    """Create a tool handler from an action function"""
    async def handler(arguments):
        return await action_func(arguments) if asyncio.iscoroutinefunction(action_func) else action_func(arguments)
    return handler