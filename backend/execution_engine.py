"""
Agentic Execution Engine - Executes workflows using Browser Agent nodes
"""
from typing import Dict, Any, List
import json
from browser_agent import execute_browser_instruction, get_browser, close_browser

class WorkflowExecutor:
    """Executes agentic workflows with sequential node processing."""
    
    def __init__(self, workflow: Dict[str, Any]):
        self.workflow = workflow
        self.nodes = {node["id"]: node for node in workflow.get("nodes", [])}
        self.edges = workflow.get("edges", [])
        self.context = {}  # Stores outputs from each node
        self.execution_log = []
        
    def topological_sort(self) -> List[str]:
        """
        Topologically sort nodes based on edges.
        Returns ordered list of node IDs.
        """
        # Build adjacency list
        graph = {node_id: [] for node_id in self.nodes}
        in_degree = {node_id: 0 for node_id in self.nodes}
        
        for edge in self.edges:
            source = edge.get("source")
            target = edge.get("target")
            if source in graph and target in graph:
                graph[source].append(target)
                in_degree[target] += 1
        
        # Kahn's algorithm
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        sorted_nodes = []
        
        while queue:
            current = queue.pop(0)
            sorted_nodes.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(sorted_nodes) != len(self.nodes):
            raise ValueError("Workflow contains a cycle - cannot execute")
        
        return sorted_nodes
    
    async def execute_node(self, node_id: str) -> Dict[str, Any]:
        """
        Execute a single node based on its type.
        
        Returns:
            Dict with execution result
        """
        node = self.nodes[node_id]
        node_type = node.get("type", "browser_agent")
        instruction = node.get("instruction", "")
        
        # Gather inputs from predecessor nodes
        inputs = self._get_node_inputs(node_id)
        
        result = {"node_id": node_id, "type": node_type, "status": "pending"}
        
        try:
            if node_type == "browser_agent":
                # Execute browser automation
                browser_result = await execute_browser_instruction(instruction, inputs)
                result["status"] = "success" if browser_result["success"] else "failed"
                result["output"] = browser_result["result"]
                result["logs"] = browser_result["logs"]
                result["action_count"] = browser_result["action_count"]
                
                # Store in context for downstream nodes
                self.context[node_id] = browser_result["result"]
                
            elif node_type == "ai_transform":
                # AI transformation using Gemini (simpler, no browser)
                from browser_agent import get_gemini_llm
                llm = get_gemini_llm()
                
                context_str = "\n".join([f"{k}: {v}" for k, v in inputs.items()])
                prompt = f"Context:\n{context_str}\n\nTransform/Process according to: {instruction}"
                
                response = await llm.ainvoke(prompt)
                result["status"] = "success"
                result["output"] = response.content
                self.context[node_id] = response.content
                
            elif node_type == "conditional":
                # LLM-based conditional routing
                from browser_agent import get_gemini_llm
                llm = get_gemini_llm()
                
                context_str = "\n".join([f"{k}: {v}" for k, v in inputs.items()])
                prompt = f"Context:\n{context_str}\n\nDecision: {instruction}\n\nRespond with ONLY 'true' or 'false'."
                
                response = await llm.ainvoke(prompt)
                decision = "true" in response.content.lower()
                
                result["status"] = "success"
                result["output"] = {"decision": decision}
                self.context[node_id] = {"decision": decision}
                
            else:
                result["status"] = "error"
                result["error"] = f"Unknown node type: {node_type}"
                
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        
        self.execution_log.append(result)
        return result
    
    def _get_node_inputs(self, node_id: str) -> Dict[str, Any]:
        """Get outputs from all predecessor nodes."""
        inputs = {}
        
        for edge in self.edges:
            if edge.get("target") == node_id:
                source_id = edge.get("source")
                if source_id in self.context:
                    inputs[source_id] = self.context[source_id]
        
        return inputs
    
    async def execute(self) -> Dict[str, Any]:
        """
        Execute entire workflow.
        
        Returns:
            Execution results and logs
        """
        try:
            # Get execution order
            execution_order = self.topological_sort()
            
            # Execute each node
            for node_id in execution_order:
                await self.execute_node(node_id)
            
            # Check for failures
            failed_nodes = [log for log in self.execution_log if log["status"] == "failed"]
            
            return {
                "status": "completed" if not failed_nodes else "partial_failure",
                "execution_order": execution_order,
                "results": self.execution_log,
                "final_context": self.context,
                "failed_count": len(failed_nodes)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "results": self.execution_log
            }
        finally:
            # Cleanup browser if needed
            pass

async def execute_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to execute a workflow.
    
    Args:
        workflow: Dict with 'nodes' and 'edges' keys
        
    Returns:
        Execution results
    """
    executor = WorkflowExecutor(workflow)
    return await executor.execute()
