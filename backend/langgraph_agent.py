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
        """Search the uploaded documents for relevant information.
        Use this tool when you need to find information from the user's documents.
        
        Args:
            query: The search query to find relevant document sections
            
        Returns:
            Relevant text excerpts from documents
        """
        logger.info(f"📄 [DOC SEARCH] Query: '{query}'")
        # The vector_store parameter passed to create_document_retriever_tool is not used here
        # as get_vector_store() is called directly inside the tool.
        # This ensures the tool can be used independently if needed.
        current_vector_store = get_vector_store() 
        try:
            results = current_vector_store.search(query, k=5, score_threshold=0.2)
            
            logger.info(f"📄 [DOC SEARCH] Found {len(results)} chunks")
            
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
                
                logger.info(f"   Chunk {i}: {text[:100]}... (File: {filename})")
                formatted.append(f"[Source {i}: {filename} (relevance: {score:.2f})]\n{text}")
                seen_files.add(filename)
            
            result_text = "\n\n".join(formatted)
            return f"Found relevant information from {len(seen_files)} document(s):\n\n{result_text}"
            
        except Exception as e:
            logger.error(f"Error in document retrieval: {e}")
            return f"Error searching documents: {str(e)}"
    
    @tool
    def crawl_website(url: str):
        """
        Crawl a website to learn comprehensive information from it.
        Use this when you need to read documentation or explore a site deeper than a single page.
        
        Args:
            url: The URL to start crawling from (e.g., 'https://docs.python.org/3/')
        """
        logger.info(f"🕷️ [AGENT-CRAWL] Requesting crawl for: {url}")
        
        # Call local API to trigger crawl
        # We use httpx to hit our own endpoint
        # The agent is running in the same process/loop, so we can't block easily?
        # Actually agent runs in main.py loop context probably?
        # We should use sync requests here inside the tool thread or async?
        # LangGraph tools are sync by default in this implementation unless using async tools
        
        try:
            # We assume the API runs on localhost:8000
            import requests
            api_url = "http://localhost:8000/api/crawl"
            response = requests.post(api_url, json={"url": url, "depth": 1}, timeout=5)
            
            if response.status_code == 200:
                return f"Started crawling {url}. The information will be available in the 'retrieve_documents' tool shortly. Please wait a moment and then use retrieve_documents to find what you need."
            else:
                return f"Failed to start crawl: Status {response.status_code}"
                
        except Exception as e:
            return f"Error triggering crawl: {e}"

    return retrieve_documents, crawl_website


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
            
            # Use DuckDuckGo HTML search via ScrapingAnt (works with Free Tier)
            # Google is often blocked on free plans
            logger.info(f"🔍 [WEB SEARCH] Query: '{query}'")
            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            api_url = f"https://api.scrapingant.com/v2/general?url={quote(search_url, safe='')}&x-api-key={SCRAPER_API_KEY}&browser=false"
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(api_url)
                
                if response.status_code != 200:
                    logger.error(f"❌ [WEB SEARCH] API Failed: Status {response.status_code}")
                    return f"Web search failed with status {response.status_code}"
                
                logger.info(f"✅ [WEB SEARCH] API Response {response.status_code} - Parsing results...")
                soup = BeautifulSoup(response.text, 'lxml')
                
            # Extract search result snippets
            results = []
            
            # Selector for DuckDuckGo HTML
            # Structure: div.result -> h2.result__title -> a.result__a (href=uddg=...)
            
            from urllib.parse import unquote, parse_qs, urlparse

            processed_sources = []
            
            try:
                # Find all result containers
                result_divs = soup.select("div.result")
                
                # If structure matches DDG
                if result_divs:
                    for div in result_divs[:5]:
                        # Title & Link
                        title_tag = div.select_one(".result__title .result__a")
                        if not title_tag: 
                            continue
                            
                        title = title_tag.get_text(strip=True)
                        raw_href = title_tag.get('href', '')
                        
                        # Extract real URL from DDG redirect
                        real_url = raw_href
                        if "duckduckgo.com/l/" in raw_href:
                            try:
                                parsed = urlparse(raw_href)
                                qs = parse_qs(parsed.query)
                                if 'uddg' in qs:
                                    real_url = qs['uddg'][0]
                            except Exception:
                                pass
                        
                        # Snippet
                        snippet_tag = div.select_one(".result__snippet")
                        snippet = snippet_tag.get_text(strip=True) if snippet_tag else "No details available."
                        
                        if len(snippet) > 20:
                            processed_sources.append({
                                "title": title,
                                "url": real_url,
                                "snippet": snippet
                            })
                            results.append(snippet)
            except Exception as e:
                logger.error(f"Error parsing DDG structure: {e}")
                
            # Fallback (Google generic selectors) if strict structure fails
            if not processed_sources:
                 for selector in ['div.BNeawe', 'div.VwiC3b', 'span.aCOpRe']:
                    if processed_sources: break
                    for div in soup.select(selector)[:5]:
                        text = div.get_text(strip=True)
                        if text and len(text) > 50:
                            processed_sources.append({
                                "title": "Web Result",
                                "url": "", 
                                "snippet": text
                            })
                            results.append(text)
                            
            logger.info(f"📉 [WEB SEARCH] Found {len(processed_sources)} results")
            
            # Format results with source tags
            # Format: [Source: Title | URL]
            formatted_text = "Web search results:\n\n"
            
            for i, src in enumerate(processed_sources, 1):
                clean_title = src['title'].replace('|', '-').replace(']', ')')
                clean_url = src['url']
                # If no URL, fallback to Result N
                source_tag = f"{clean_title} | {clean_url}" if clean_url else f"Web Search Result {i}"
                
                formatted_text += f"[Source: {source_tag}]\n{src['snippet']}\n\n"
            
            if processed_sources:
                return formatted_text
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
    # Now returns tuple: (retrieve_documents, crawl_website)
    doc_tool, crawl_tool = create_document_retriever_tool(vector_store)
    tools = [doc_tool, crawl_tool]
    
    # Add web search if configured
    if SCRAPER_API_KEY:
        web_tool = create_web_search_tool()
        tools.append(web_tool)
    
    # Create LLM with tools
    llm = create_llm()
    llm_with_tools = llm.bind_tools(tools)
    
    # System prompt
    system_prompt = """You are an intelligent assistant capable of document analysis, web search, and WEBSITE CRAWLING.

Guidelines:
1. ALWAYS attempts to search the documents first using retrieve_documents.
2. If the user asks to "crawl", "learn", "study", or "read" a website/documentation, use the `crawl_website` tool.
   - After triggering a crawl, inform the user you have started the process and they should wait a moment before searching the new content.
3. If documents lack info, USE `search_web` for quick facts/news.
4. Use `retrieve_documents` to find information from both user uploads AND previously crawled sites.
5. Combine information from all sources.

When responding:
- Start with a direct, detailed answer based on the facts found.
- Do NOT just say "The information is available on..." or "Sources include...".
- ACTUALLY summarized the content.
- Mention source types ("Uploaded Documents", "Crawled Content", "Web Search") only as a citation at the end."""
    
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
                content = msg.content
                if "[Source" in content:
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith("[Source"):
                            # Handle Document Source
                            if "(relevance:" in line:
                                try:
                                    inner = line[1:-1]
                                    if ":" in inner:
                                        _, file_part = inner.split(":", 1)
                                        if "(relevance" in file_part:
                                            filename = file_part.split("(relevance")[0].strip()
                                            sources.append({"filename": filename, "type": "document"})
                                except Exception:
                                    pass
                            
                            # Handle Web Source: [Source: Title | URL]
                            elif "|" in line:
                                try:
                                    # [Source: Title | URL]
                                    inner = line[8:-1] # Remove [Source: and ]
                                    if "|" in inner:
                                        title, url = inner.split("|", 1)
                                        sources.append({
                                            "filename": title.strip(), 
                                            "url": url.strip(), 
                                            "type": "web"
                                        })
                                except Exception:
                                    pass
                            
                            # Fallback Web Source
                            elif "Web Search" in line:
                                sources.append({"filename": "Web Search", "type": "web"})
        
        # Deduplicate
        unique_sources = []
        seen = set()
        for s in sources:
            key = s.get("url") or s.get("filename")
            if key and key not in seen:
                seen.add(key)
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
        has_documents = stats.get("total_chunks", 0) > 0
        
        # If no documents AND no web search, then we can't do anything
        if not has_documents and not SCRAPER_API_KEY:
            return AgentResult(
                content="No documents have been uploaded yet, and web search is not configured. Please upload some documents first.",
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
