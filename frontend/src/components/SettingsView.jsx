import { useState, useEffect } from 'react';
import './SettingsView.css';

const Icons = {
    file: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6" /></svg>,
    chat: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>,
    message: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" /></svg>,
    key: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" /></svg>,
    bot: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 8V4M8 12H4m16 0h-4M12 16v4M9 9l-2-2m10 2l2-2m-10 8l-2 2m10-2l2 2" /><circle cx="12" cy="12" r="4" /></svg>,
    check: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12" /></svg>,
    x: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>,
    save: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" /><polyline points="17,21 17,13 7,13 7,21" /><polyline points="7,3 7,8 15,8" /></svg>,
    refresh: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" /><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" /></svg>,
    eye: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>,
    eyeOff: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>,
};

export default function SettingsView({ stats }) {
    const [settings, setSettings] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState(null);
    const [showGroqKey, setShowGroqKey] = useState(false);
    const [showScraperKey, setShowScraperKey] = useState(false);

    // Form state
    const [groqApiKey, setGroqApiKey] = useState('');
    const [scraperAntApiKey, setScraperAntApiKey] = useState('');
    const [selectedModel, setSelectedModel] = useState('');
    const [n8nBaseUrl, setN8nBaseUrl] = useState('');
    const [n8nUploadWebhookId, setN8nUploadWebhookId] = useState('');
    const [n8nChatWebhookPath, setN8nChatWebhookPath] = useState('');

    const shortcuts = [
        { action: 'Send message', keys: ['Enter'] },
        { action: 'New line', keys: ['Shift', 'Enter'] },
        { action: 'New chat', keys: ['Ctrl', 'N'] },
        { action: 'Search documents', keys: ['Ctrl', 'K'] },
    ];

    useEffect(() => {
        fetchSettings();
    }, []);

    const fetchSettings = async () => {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();
            setSettings(data);
            setGroqApiKey(data.groq_api_key || '');
            setScraperAntApiKey(data.scraper_ant_api_key || '');
            setSelectedModel(data.llm_model || 'llama-3.3-70b-versatile');
            setN8nBaseUrl(data.n8n_base_url || 'http://localhost:5678');
            setN8nUploadWebhookId(data.n8n_upload_webhook_id || '');
            setN8nChatWebhookPath(data.n8n_chat_webhook_path || '');
        } catch (error) {
            console.error('Failed to fetch settings:', error);
            setMessage({ type: 'error', text: 'Failed to load settings' });
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setMessage(null);

        try {
            const response = await fetch('/api/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    groq_api_key: groqApiKey.startsWith('*') ? null : groqApiKey,
                    scraper_ant_api_key: scraperAntApiKey.startsWith('*') ? null : scraperAntApiKey,
                    llm_model: selectedModel,
                    n8n_base_url: n8nBaseUrl,
                    n8n_upload_webhook_id: n8nUploadWebhookId,
                    n8n_chat_webhook_path: n8nChatWebhookPath,
                }),
            });

            const data = await response.json();

            if (response.ok) {
                setMessage({ type: 'success', text: data.message });
                fetchSettings(); // Refresh settings
            } else {
                setMessage({ type: 'error', text: data.detail || 'Failed to save settings' });
            }
        } catch (error) {
            setMessage({ type: 'error', text: 'Failed to save settings' });
        } finally {
            setSaving(false);
        }
    };

    const getModelInfo = (modelId) => {
        return settings?.available_models?.find(m => m.id === modelId);
    };

    const currentModelInfo = getModelInfo(selectedModel);

    if (loading) {
        return (
            <div className="settings-view">
                <header className="settings-header">
                    <h1 className="settings-header-title">Settings</h1>
                </header>
                <div className="settings-content">
                    <div className="settings-loading">Loading settings...</div>
                </div>
            </div>
        );
    }

    return (
        <div className="settings-view">
            {/* Header */}
            <header className="settings-header">
                <h1 className="settings-header-title">Settings</h1>
                <button className="settings-save-btn" onClick={handleSave} disabled={saving}>
                    {Icons.save}
                    {saving ? 'Saving...' : 'Save Changes'}
                </button>
            </header>

            {/* Message */}
            {message && (
                <div className={`settings-message ${message.type}`}>
                    {message.type === 'success' ? Icons.check : Icons.x}
                    {message.text}
                </div>
            )}

            {/* Content */}
            <div className="settings-content">
                <div className="settings-container">

                    {/* API Keys Section */}
                    <section className="settings-section">
                        <div className="section-header">
                            <h2 className="section-title">{Icons.key} API Configuration</h2>
                            <p className="section-subtitle">Configure your AI provider API keys</p>
                        </div>
                        <div className="section-body">
                            <div className="form-group">
                                <label className="form-label">
                                    Groq API Key
                                    {settings?.groq_api_key_set && <span className="status-badge success">Configured</span>}
                                </label>
                                <div className="input-with-toggle">
                                    <input
                                        type={showGroqKey ? "text" : "password"}
                                        className="form-input"
                                        value={groqApiKey}
                                        onChange={(e) => setGroqApiKey(e.target.value)}
                                        placeholder="gsk_xxxxxxxxxxxxxxxx"
                                    />
                                    <button
                                        className="toggle-visibility"
                                        onClick={() => setShowGroqKey(!showGroqKey)}
                                        type="button"
                                    >
                                        {showGroqKey ? Icons.eyeOff : Icons.eye}
                                    </button>
                                </div>
                                <p className="form-hint">Get your API key from <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer">console.groq.com</a></p>
                            </div>

                            <div className="form-group">
                                <label className="form-label">
                                    ScrapingAnt API Key
                                    {settings?.scraper_ant_api_key_set && <span className="status-badge success">Configured</span>}
                                    <span className="optional-badge">Optional</span>
                                </label>
                                <div className="input-with-toggle">
                                    <input
                                        type={showScraperKey ? "text" : "password"}
                                        className="form-input"
                                        value={scraperAntApiKey}
                                        onChange={(e) => setScraperAntApiKey(e.target.value)}
                                        placeholder="xxxxxxxxxxxxxxxxxxxxxxxx"
                                    />
                                    <button
                                        className="toggle-visibility"
                                        onClick={() => setShowScraperKey(!showScraperKey)}
                                        type="button"
                                    >
                                        {showScraperKey ? Icons.eyeOff : Icons.eye}
                                    </button>
                                </div>
                                <p className="form-hint">For web search fallback. Get from <a href="https://scrapingant.com" target="_blank" rel="noopener noreferrer">scrapingant.com</a></p>
                            </div>
                        </div>
                    </section>

                    {/* Model Selection Section */}
                    <section className="settings-section">
                        <div className="section-header">
                            <h2 className="section-title">{Icons.bot} AI Model</h2>
                            <p className="section-subtitle">Select the LLM model for chat responses</p>
                        </div>
                        <div className="section-body">
                            <div className="form-group">
                                <label className="form-label">Language Model</label>
                                <select
                                    className="form-select"
                                    value={selectedModel}
                                    onChange={(e) => setSelectedModel(e.target.value)}
                                >
                                    <optgroup label="Production Models">
                                        {settings?.available_models?.filter(m => m.type === 'production').map(model => (
                                            <option key={model.id} value={model.id}>
                                                {model.name} ({model.provider}) - {model.speed} t/s
                                            </option>
                                        ))}
                                    </optgroup>
                                    <optgroup label="Preview Models">
                                        {settings?.available_models?.filter(m => m.type === 'preview').map(model => (
                                            <option key={model.id} value={model.id}>
                                                {model.name} ({model.provider}) - {model.speed} t/s
                                            </option>
                                        ))}
                                    </optgroup>
                                </select>
                            </div>

                            {currentModelInfo && (
                                <div className="model-info-card">
                                    <div className="model-info-header">
                                        <span className="model-name">{currentModelInfo.name}</span>
                                        <span className={`model-type ${currentModelInfo.type}`}>
                                            {currentModelInfo.type}
                                        </span>
                                    </div>
                                    <div className="model-info-grid">
                                        <div className="model-info-item">
                                            <span className="label">Provider</span>
                                            <span className="value">{currentModelInfo.provider}</span>
                                        </div>
                                        <div className="model-info-item">
                                            <span className="label">Speed</span>
                                            <span className="value">{currentModelInfo.speed} tokens/sec</span>
                                        </div>
                                        <div className="model-info-item">
                                            <span className="label">Context</span>
                                            <span className="value">{(currentModelInfo.context / 1024).toFixed(0)}K tokens</span>
                                        </div>
                                        <div className="model-info-item">
                                            <span className="label">Price</span>
                                            <span className="value">
                                                ${currentModelInfo.input_price}/1M in, ${currentModelInfo.output_price}/1M out
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </section>

                    {/* n8n Configuration */}
                    <section className="settings-section">
                        <div className="section-header">
                            <h2 className="section-title">n8n Configuration</h2>
                            <p className="section-subtitle">Configure n8n workflow integration (optional)</p>
                        </div>
                        <div className="section-body">
                            <div className="form-group">
                                <label className="form-label">n8n Base URL</label>
                                <input
                                    type="text"
                                    className="form-input"
                                    value={n8nBaseUrl}
                                    onChange={(e) => setN8nBaseUrl(e.target.value)}
                                    placeholder="http://localhost:5678"
                                />
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label className="form-label">Upload Webhook ID</label>
                                    <input
                                        type="text"
                                        className="form-input"
                                        value={n8nUploadWebhookId}
                                        onChange={(e) => setN8nUploadWebhookId(e.target.value)}
                                        placeholder="your-upload-webhook-id"
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Chat Webhook Path</label>
                                    <input
                                        type="text"
                                        className="form-input"
                                        value={n8nChatWebhookPath}
                                        onChange={(e) => setN8nChatWebhookPath(e.target.value)}
                                        placeholder="webhook/your-chat-path"
                                    />
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Stats Section */}
                    <section className="settings-section">
                        <div className="section-header">
                            <h2 className="section-title">Statistics</h2>
                            <p className="section-subtitle">Overview of your usage</p>
                        </div>
                        <div className="section-body">
                            <div className="stats-grid">
                                <div className="stat-card">
                                    <div className="stat-icon">{Icons.file}</div>
                                    <div className="stat-number">{stats.documents}</div>
                                    <div className="stat-name">Documents</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-icon">{Icons.chat}</div>
                                    <div className="stat-number">{stats.conversations}</div>
                                    <div className="stat-name">Conversations</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-icon">{Icons.message}</div>
                                    <div className="stat-number">{stats.messages}</div>
                                    <div className="stat-name">Messages</div>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Keyboard Shortcuts */}
                    <section className="settings-section">
                        <div className="section-header">
                            <h2 className="section-title">Keyboard Shortcuts</h2>
                            <p className="section-subtitle">Quick actions</p>
                        </div>
                        <div className="section-body">
                            <div className="shortcuts-list">
                                {shortcuts.map((s, i) => (
                                    <div key={i} className="shortcut-item">
                                        <span className="shortcut-action">{s.action}</span>
                                        <div className="shortcut-keys">
                                            {s.keys.map((k, j) => (
                                                <span key={j} className="key">{k}</span>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </section>

                    {/* About Section */}
                    <section className="settings-section">
                        <div className="section-header">
                            <h2 className="section-title">About</h2>
                            <p className="section-subtitle">Application information</p>
                        </div>
                        <div className="section-body">
                            <div className="about-content">
                                <div className="about-brand">
                                    <div className="about-logo">DI</div>
                                    <div className="about-info">
                                        <div className="about-name">Document Intelligence</div>
                                        <div className="about-version">Version 1.0.0</div>
                                    </div>
                                </div>
                                <p className="about-description">
                                    AI-powered document analysis and chat assistant with LangGraph RAG fallback. Upload documents and ask questions to get intelligent answers based on your content.
                                </p>
                            </div>
                        </div>
                    </section>

                </div>
            </div>
        </div>
    );
}
