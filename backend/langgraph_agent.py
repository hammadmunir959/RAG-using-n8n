"""
LangGraph ReAct Agent for document Q&A with fallback capabilities.
Implements a Reasoning + Acting agent that can:
1. Retrieve relevant context from ChromaDB
2. Optionally search the web via ScraperAPI
3. Generate responses using Groq LLM
"""
import os
import logging
from typing import List, Dict, Any, Optional, TypedDict, Annotated, Sequence
from operator import add

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
SCRAPER_API_KEY = os.getenv("SCRAPER_ANT_API_KEY", "")  # ScrapingAnt API key
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


class AgentState(TypedDict):
    """State for the ReAct agent."""
    messages: Annotated[Sequence[BaseMessage], add]
    context: str
    sources: List[Dict[str, Any]]
    query: str


class AgentResult:
    """Result from agent execution."""
    def __init__(self, content: str, sources: List[Dict[str, Any]] = None, error: str = None):
        self.content = content
        self.sources = sources or []
        self.error = error


def create_document_retriever_tool(vector_store: VectorStore):
    """Create a tool that retrieves relevant document chunks."""
    
    @tool
    def retrieve_documents(query: str) -> str:
        """
        Search uploaded documents for relevant information.
        Use this tool when you need to find information from the user's documents.
        
        Args:
            query: The search query to find relevant document sections
            
        Returns:
            Relevant text excerpts from documents
        """
        try:
            results = vector_store.search(query, k=5, score_threshold=0.2)
            
            if not results:
                return "No relevant information found in the uploaded documents."
            
            # Format results
            formatted = []
            seen_files = set()
            
            for i, r in enumerate(results, 1):
                filename = r.get("filename", "Unknown")
                text = r.get("text", "")
                score = r.get("score", 0)
                
                # Truncate long text
                if len(text) > 500:
                    text = text[:500] + "..."
                
                formatted.append(f"[Source {i}: {filename} (relevance: {score:.2f})]\n{text}")
                seen_files.add(filename)
            
            result_text = "\n\n".join(formatted)
            return f"Found relevant information from {len(seen_files)} document(s):\n\n{result_text}"
            
        except Exception as e:
            logger.error(f"Error in document retrieval: {e}")
            return f"Error searching documents: {str(e)}"
    
    return retrieve_documents


def create_web_search_tool():
    """Create a tool that searches the web via ScrapingAnt."""
    
    @tool
    def search_web(query: str) -> str:
        """
        Search the web for real-time information.
        Use this tool when:
        - The documents don't contain the needed information
        - You need current/real-time data
        - The user asks about something not in their documents
        
        Args:
            query: The search query
            
        Returns:
            Search results from the web
        """
        if not SCRAPER_API_KEY:
            return "Web search is not configured. Please answer based on document context only."
        
        try:
            import httpx
            from urllib.parse import quote
            from bs4 import BeautifulSoup
            
            # Use Google search via ScrapingAnt
            search_url = f"https://www.google.com/search?q={quote(query)}"
            api_url = f"https://api.scrapingant.com/v2/general?url={quote(search_url, safe='')}&x-api-key={SCRAPER_API_KEY}&browser=false"
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(api_url)
                
                if response.status_code != 200:
                    return f"Web search failed with status {response.status_code}"
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Extract search result snippets
                results = []
                
                # Try different Google result selectors
                for selector in ['div.BNeawe', 'div.VwiC3b', 'span.aCOpRe', 'div.s']:
                    for div in soup.select(selector)[:5]:
                        text = div.get_text(strip=True)
                        if text and len(text) > 50:
                            results.append(text)
                    if results:
                        break
                
                # Fallback: get any substantial text
                if not results:
                    for p in soup.find_all(['p', 'span', 'div'])[:20]:
                        text = p.get_text(strip=True)
                        if text and len(text) > 100:
                            results.append(text[:500])
                            if len(results) >= 3:
                                break
                
                if results:
                    return "Web search results:\n\n" + "\n\n".join(results[:3])
                else:
                    return "No useful results found from web search."
                    
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return f"Web search failed: {str(e)}"
    
    return search_web


def create_llm() -> ChatGroq:
    """Create the Groq LLM instance."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is required")
    
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model_name=LLM_MODEL,
        temperature=0.3,
        max_tokens=2048
    )


def create_react_agent(vector_store: VectorStore) -> StateGraph:
    """
    Create the ReAct agent graph.
    
    The agent follows the Reasoning + Acting pattern:
    1. Receives user query
    2. Decides which tool to use (document retrieval or web search)
    3. Executes tool and gets results
    4. Generates response based on context
    """
    
    # Create tools
    doc_tool = create_document_retriever_tool(vector_store)
    tools = [doc_tool]
    
    # Add web search if configured
    if SCRAPER_API_KEY:
        web_tool = create_web_search_tool()
        tools.append(web_tool)
    
    # Create LLM with tools
    llm = create_llm()
    llm_with_tools = llm.bind_tools(tools)
    
    # System prompt
    system_prompt = """You are an intelligent document assistant. Your role is to help users understand and query their uploaded documents.

Guidelines:
1. ALWAYS search the documents first using the retrieve_documents tool before answering questions
2. Base your answers on the document content when available
3. If documents don't contain the answer, clearly state that
4. Cite your sources by mentioning the document names
5. Be concise but thorough in your responses
6. If web search is available and documents don't help, you may search the web

When responding:
- Start with a direct answer to the question
- Support your answer with relevant quotes or references from documents
- If multiple documents are relevant, synthesize the information
- Be honest about what the documents do and don't contain"""
    
    def should_continue(state: AgentState) -> str:
        """Determine if we should continue to tools or end."""
        messages = state["messages"]
        last_message = messages[-1]
        
        # If there are tool calls, continue to tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        
        # Otherwise, end
        return "end"
    
    def call_agent(state: AgentState) -> Dict[str, Any]:
        """Call the LLM agent."""
        messages = state["messages"]
        
        # Add system message if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + list(messages)
        
        response = llm_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    def extract_sources(state: AgentState) -> Dict[str, Any]:
        """Extract source information from tool calls."""
        sources = []
        
        for msg in state["messages"]:
            if hasattr(msg, 'content') and isinstance(msg.content, str):
                # Search for source markers in the content
                # Format: [Source N: filename.pdf (relevance: X.XX)]
                content = msg.content
                if "[Source" in content:
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith("[Source") and "(relevance:" in line:
                            try:
                                # Parse: [Source 1: filename.pdf (relevance: 0.85)]
                                # 1. Remove [Source and ]
                                inner = line[1:-1] # Source 1: filename.pdf (relevance: 0.85)
                                # 2. Split by first colon to get content
                                if ":" in inner:
                                    _, file_part = inner.split(":", 1)
                                    # file_part = " filename.pdf (relevance: 0.85)"
                                    # 3. Split by (relevance to separate filename
                                    if "(relevance" in file_part:
                                        filename = file_part.split("(relevance")[0].strip()
                                        sources.append({"filename": filename})
                            except Exception as e:
                                logger.warning(f"Failed to parse source line: {line} - {e}")
        
        # Deduplicate
        unique_sources = []
        seen = set()
        for s in sources:
            if s.get("filename") and s["filename"] not in seen:
                seen.add(s["filename"])
                unique_sources.append(s)
        
        return {"sources": unique_sources}
    
    # Build the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("extract_sources", extract_sources)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": "extract_sources"
        }
    )
    
    # Tools always go back to agent for next decision
    workflow.add_edge("tools", "agent")
    
    # Extract sources leads to END
    workflow.add_edge("extract_sources", END)
    
    return workflow.compile()


async def run_agent(
    query: str,
    vector_store: Optional[VectorStore] = None,
    conversation_history: Optional[List[Dict]] = None
) -> AgentResult:
    """
    Run the ReAct agent to answer a query.
    
    Args:
        query: User's question
        vector_store: VectorStore instance (uses global if not provided)
        conversation_history: Previous messages for context
        
    Returns:
        AgentResult with content and sources
    """
    try:
        # Get vector store
        if vector_store is None:
            vector_store = get_vector_store()
        
        # Check if we have any documents
        stats = vector_store.get_stats()
        if stats.get("total_chunks", 0) == 0:
            return AgentResult(
                content="No documents have been uploaded yet. Please upload some documents first, and I'll be able to help you analyze them.",
                sources=[]
            )
        
        # Create the agent
        agent = create_react_agent(vector_store)
        
        # Build messages
        messages = []
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))
        
        # Add current query
        messages.append(HumanMessage(content=query))
        
        # Initial state
        initial_state = {
            "messages": messages,
            "context": "",
            "sources": [],
            "query": query
        }
        
        # Run the agent
        logger.info(f"Running LangGraph agent for query: {query[:100]}...")
        result = await agent.ainvoke(initial_state)
        
        # Extract final response
        final_messages = result.get("messages", [])
        sources = result.get("sources", [])
        
        # Find the last AI message
        response_content = "I couldn't generate a response. Please try again."
        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage) and msg.content:
                # Skip tool call messages
                if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                    response_content = msg.content
                    break
        
        logger.info(f"Agent completed. Response length: {len(response_content)}, Sources: {len(sources)}")
        
        return AgentResult(content=response_content, sources=sources)
        
    except ValueError as e:
        # Missing API key
        logger.error(f"Configuration error: {e}")
        return AgentResult(
            content="The AI assistant is not properly configured. Please check that GROQ_API_KEY is set.",
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Agent execution error: {e}", exc_info=True)
        return AgentResult(
            content=f"An error occurred while processing your request: {str(e)}",
            error=str(e)
        )


def is_langgraph_available() -> bool:
    """Check if LangGraph fallback is properly configured."""
    return bool(GROQ_API_KEY)


def get_langgraph_status() -> Dict[str, Any]:
    """Get status of LangGraph configuration."""
    return {
        "available": is_langgraph_available(),
        "groq_configured": bool(GROQ_API_KEY),
        "web_search_configured": bool(SCRAPER_API_KEY),
        "model": LLM_MODEL
    }
