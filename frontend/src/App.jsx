import { useState, useEffect, useCallback } from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import DocumentsView from './components/DocumentsView';
import UploadView from './components/UploadView';
import SettingsView from './components/SettingsView';

function App() {
  const [view, setView] = useState('chat');
  const [documents, setDocuments] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({ documents: 0, conversations: 0, messages: 0 });

  // Fetch all data
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [docsRes, convsRes] = await Promise.all([
        fetch('/api/documents'),
        fetch('/api/conversations')
      ]);

      const docsData = await docsRes.json();
      const convsData = await convsRes.json();

      if (docsData.success) {
        setDocuments(docsData.documents || []);
      }
      if (convsData.success) {
        setConversations(convsData.conversations || []);
        // Calculate total messages
        const totalMessages = (convsData.conversations || []).reduce(
          (sum, c) => sum + (c.message_count || 0), 0
        );
        setStats({
          documents: docsData.documents?.length || 0,
          conversations: convsData.conversations?.length || 0,
          messages: totalMessages
        });
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Document actions
  const deleteDocument = async (id) => {
    try {
      const res = await fetch(`/api/documents/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.id !== id));
        setStats(prev => ({ ...prev, documents: prev.documents - 1 }));
      }
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  // Conversation actions
  const createConversation = () => {
    setActiveConversationId(null);
    setView('chat');
  };

  const selectConversation = (id) => {
    setActiveConversationId(id);
    setView('chat');
  };

  const deleteConversation = async (id) => {
    try {
      const res = await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setConversations(prev => prev.filter(c => c.id !== id));
        if (activeConversationId === id) {
          setActiveConversationId(null);
        }
        setStats(prev => ({ ...prev, conversations: prev.conversations - 1 }));
      }
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  const onConversationCreated = (id) => {
    setActiveConversationId(id);
    fetchData(); // Refresh to get new conversation
  };

  const onUploadComplete = () => {
    fetchData();
    setView('documents');
  };

  // Render view
  const renderView = () => {
    switch (view) {
      case 'chat':
        return (
          <ChatView
            conversationId={activeConversationId}
            onConversationCreated={onConversationCreated}
            documentsCount={documents.length}
          />
        );
      case 'documents':
        return (
          <DocumentsView
            documents={documents}
            onDelete={deleteDocument}
            onRefresh={fetchData}
            isLoading={isLoading}
            onUploadClick={() => setView('upload')}
          />
        );
      case 'upload':
        return (
          <UploadView
            onComplete={onUploadComplete}
            onCancel={() => setView('documents')}
          />
        );
      case 'settings':
        return <SettingsView stats={stats} />;
      default:
        return null;
    }
  };

  return (
    <div className="app">
      <Sidebar
        activeView={view}
        onViewChange={setView}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={selectConversation}
        onNewConversation={createConversation}
        onDeleteConversation={deleteConversation}
        stats={stats}
      />
      <main className="app-main">
        {renderView()}
      </main>
    </div>
  );
}

export default App;
