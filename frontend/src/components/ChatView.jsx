import { useState, useEffect, useRef } from 'react';
import './ChatView.css';

const Icons = {
    chat: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>,
    send: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>,
    file: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6" /></svg>,
    refresh: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M23 4v6h-6M1 20v-6h6" /><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" /></svg>,
    copy: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" /></svg>,
    ai: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></svg>,
    docs: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 016.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" /></svg>,
};

export default function ChatView({ conversationId, onConversationCreated, documentsCount }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [currentConvId, setCurrentConvId] = useState(conversationId);
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);

    // Scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Load conversation
    useEffect(() => {
        setCurrentConvId(conversationId);
        if (conversationId) {
            loadConversation(conversationId);
        } else {
            setMessages([]);
        }
    }, [conversationId]);

    const loadConversation = async (id) => {
        setIsLoading(true);
        try {
            const res = await fetch(`/api/conversations/${id}`);
            const data = await res.json();
            if (data.success) {
                setMessages(data.conversation.messages || []);
            }
        } catch (e) {
            console.error('Load failed:', e);
        }
        setIsLoading(false);
    };

    // Send message
    const sendMessage = async () => {
        if (!input.trim() || isSending) return;

        const userMsg = input.trim();
        setInput('');
        setIsSending(true);

        // Add user message
        const tempUser = {
            id: Date.now(),
            role: 'user',
            content: userMsg,
            created_at: new Date().toISOString()
        };
        setMessages(prev => [...prev, tempUser]);

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userMsg,
                    conversation_id: currentConvId
                })
            });

            const data = await res.json();

            if (data.success) {
                if (!currentConvId && data.conversation_id) {
                    setCurrentConvId(data.conversation_id);
                    onConversationCreated?.(data.conversation_id);
                }

                const assistantMsg = {
                    id: data.message_id || Date.now() + 1,
                    role: 'assistant',
                    content: data.response,
                    created_at: new Date().toISOString(),
                    sources: data.sources || []
                };
                setMessages(prev => [...prev, assistantMsg]);
            } else {
                setMessages(prev => [...prev, {
                    id: Date.now() + 1,
                    role: 'assistant',
                    content: 'An error occurred. Please try again.',
                    created_at: new Date().toISOString()
                }]);
            }
        } catch (e) {
            console.error('Send failed:', e);
            setMessages(prev => [...prev, {
                id: Date.now() + 1,
                role: 'assistant',
                content: 'Failed to connect to server. Is the backend running?',
                created_at: new Date().toISOString()
            }]);
        }

        setIsSending(false);
        textareaRef.current?.focus();
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    const handleSuggestion = (text) => {
        setInput(text);
        textareaRef.current?.focus();
    };

    // Auto-resize textarea
    const handleInput = (e) => {
        setInput(e.target.value);
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
    };

    const formatTime = (dateStr) => {
        return new Date(dateStr).toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit'
        });
    };

    const suggestions = [
        "Summarize the uploaded documents",
        "What are the key points?",
        "Find specific information about...",
        "Compare the documents"
    ];

    if (isLoading) {
        return (
            <div className="chat-view">
                <div className="chat-loading">
                    <div className="spinner"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="chat-view">
            {/* Header */}
            <header className="chat-header">
                <div className="chat-header-left">
                    <h1 className="chat-header-title">
                        {currentConvId ? 'Chat' : 'New Chat'}
                    </h1>
                    <div className="chat-header-meta">
                        {Icons.docs}
                        <span>{documentsCount} documents available</span>
                    </div>
                </div>
                <div className="chat-header-right">
                    <button className="header-action" title="Refresh">
                        {Icons.refresh}
                    </button>
                </div>
            </header>

            {/* Messages or Empty */}
            {messages.length === 0 ? (
                <div className="chat-empty">
                    <div className="empty-icon">{Icons.chat}</div>
                    <h2 className="empty-title">Start a conversation</h2>
                    <p className="empty-subtitle">
                        Ask questions about your uploaded documents. The AI will analyze and provide intelligent answers.
                    </p>
                    <div className="suggestions-grid">
                        {suggestions.map((s, i) => (
                            <button
                                key={i}
                                className="suggestion-btn"
                                onClick={() => handleSuggestion(s)}
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                </div>
            ) : (
                <div className="chat-messages">
                    <div className="messages-container">
                        {messages.map(msg => (
                            <div key={msg.id} className={`message ${msg.role}`}>
                                <div className="message-avatar">
                                    {msg.role === 'user' ? 'U' : 'AI'}
                                </div>
                                <div className="message-body">
                                    <div className="message-content">
                                        <div className="message-text">{msg.content}</div>
                                        {msg.sources?.length > 0 && (
                                            <div className="message-sources">
                                                <div className="sources-header">Sources</div>
                                                <div className="sources-tags">
                                                    {msg.sources.map((s, i) => {
                                                        const isLink = !!s.url;
                                                        const Tag = isLink ? 'a' : 'span';
                                                        const props = isLink ? { href: s.url, target: '_blank', rel: 'noopener noreferrer' } : {};

                                                        return (
                                                            <Tag key={i} className={`source-tag ${isLink ? 'source-link' : ''}`} {...props}>
                                                                {isLink ? (
                                                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '6px', width: '14px', height: '14px' }}>
                                                                        <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" />
                                                                        <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" />
                                                                    </svg>
                                                                ) : Icons.file}
                                                                {s.filename || `Doc ${s.id}`}
                                                            </Tag>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                    <div className="message-time">{formatTime(msg.created_at)}</div>
                                </div>
                            </div>
                        ))}

                        {isSending && (
                            <div className="typing-indicator">
                                <div className="message-avatar" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)' }}>
                                    AI
                                </div>
                                <div className="typing-bubble">
                                    <span className="typing-dot"></span>
                                    <span className="typing-dot"></span>
                                    <span className="typing-dot"></span>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>
                </div>
            )}

            {/* Input */}
            <div className="chat-input-area">
                <div className="input-container">
                    <div className="input-wrapper">
                        <textarea
                            ref={textareaRef}
                            className="chat-textarea"
                            placeholder="Type your message..."
                            value={input}
                            onChange={handleInput}
                            onKeyDown={handleKeyDown}
                            rows={1}
                            disabled={isSending}
                        />
                        <button
                            className="send-btn"
                            onClick={sendMessage}
                            disabled={!input.trim() || isSending}
                        >
                            {Icons.send}
                        </button>
                    </div>
                    <div className="input-hint">
                        Press Enter to send, Shift+Enter for new line
                    </div>
                </div>
            </div>
        </div>
    );
}
