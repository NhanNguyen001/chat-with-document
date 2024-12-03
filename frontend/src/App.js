import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

// Configure axios defaults
const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000,
});

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [serverStatus, setServerStatus] = useState('checking');
  const [hasDocuments, setHasDocuments] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authSuccess, setAuthSuccess] = useState('');
  const [activeSection, setActiveSection] = useState('chat');
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const chatContainerRef = useRef(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      setIsAuthenticated(true);
      checkServerConnection();
      fetchDocuments();
    }
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await api.get('/documents');
      setDocuments(response.data);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setMessages(prev => [...prev, {
        text: response.data.message,
        isUser: false
      }]);
      setHasDocuments(true);
      fetchDocuments();
    } catch (error) {
      console.error('Error uploading document:', error);
      const errorMessage = error.response?.data?.detail || 
        error.message || 
        'Error uploading document';
      
      setMessages(prev => [...prev, {
        text: errorMessage,
        isUser: false
      }]);
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleDeleteDocument = async (documentId) => {
    try {
      await api.delete(`/documents/${documentId}`);
      fetchDocuments();
      setMessages(prev => [...prev, {
        text: 'Document deleted successfully',
        isUser: false
      }]);
    } catch (error) {
      console.error('Error deleting document:', error);
      setMessages(prev => [...prev, {
        text: error.response?.data?.detail || 'Error deleting document',
        isUser: false
      }]);
    }
  };

  const checkServerConnection = async () => {
    try {
      const response = await api.get('/health');
      setServerStatus('connected');
      setHasDocuments(response.data.has_documents);
    } catch (error) {
      console.error('Server connection error:', error);
      setServerStatus('disconnected');
      setHasDocuments(false);
    }
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');

    try {
      if (authMode === 'login') {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await api.post('/token', formData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        });

        const { access_token } = response.data;
        localStorage.setItem('token', access_token);
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
        setIsAuthenticated(true);
        checkServerConnection();
      } else if (authMode === 'register') {
        if (password !== confirmPassword) {
          setAuthError('Passwords do not match');
          return;
        }

        await api.post('/register', {
          username,
          email,
          password,
        });

        setAuthSuccess('Registration successful! Please login.');
        setAuthMode('login');
        setPassword('');
        setConfirmPassword('');
      }
    } catch (error) {
      console.error('Auth error:', error);
      setAuthError(error.response?.data?.detail || 'Authentication failed');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    delete api.defaults.headers.common['Authorization'];
    setIsAuthenticated(false);
    setMessages([]);
    setServerStatus('checking');
  };

  const sendMessage = async () => {
    if (!input.trim() || sending) return;

    if (!hasDocuments) {
      setMessages(prev => [...prev, {
        text: 'Please upload some documents first before chatting.',
        isUser: false
      }]);
      return;
    }

    const userMessage = { text: input, isUser: true };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setSending(true);

    try {
      const response = await api.post('/chat', {
        message: input
      });

      const botMessage = { text: response.data.response, isUser: false };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = error.response?.data?.detail || 
        error.message || 
        'Error communicating with the server';
      
      setMessages(prev => [...prev, {
        text: errorMessage,
        isUser: false
      }]);

      if (error.message.includes('Network Error')) {
        checkServerConnection();
      }
    } finally {
      setSending(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto mt-20 p-6 bg-white rounded-lg shadow-md">
        <div className="flex border-b mb-6">
          <button
            className={`flex-1 pb-2 ${authMode === 'login' ? 'border-b-2 border-blue-500 text-blue-500' : 'text-gray-500'}`}
            onClick={() => setAuthMode('login')}
          >
            Login
          </button>
          <button
            className={`flex-1 pb-2 ${authMode === 'register' ? 'border-b-2 border-blue-500 text-blue-500' : 'text-gray-500'}`}
            onClick={() => setAuthMode('register')}
          >
            Register
          </button>
        </div>

        {authError && <div className="mb-4 text-center text-red-500">{authError}</div>}
        {authSuccess && <div className="mb-4 text-center text-green-500">{authSuccess}</div>}

        <form onSubmit={handleAuth} className="space-y-4">
          {authMode === 'register' && (
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="input"
            />
          )}
          
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="input"
          />
          
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="input"
          />
          
          {authMode === 'register' && (
            <input
              type="password"
              placeholder="Confirm Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="input"
            />
          )}

          <button type="submit" className="btn-primary w-full">
            {authMode === 'login' ? 'Login' : 'Register'}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <nav className="nav-container">
        <div className="nav-content">
          <h1 className="nav-title">Chat with AI</h1>
          <div className="nav-buttons">
            <button
              className={`menu-item ${activeSection === 'chat' ? 'menu-item-active' : 'menu-item-inactive'}`}
              onClick={() => setActiveSection('chat')}
            >
              Chat
            </button>
            <button
              className={`menu-item ${activeSection === 'documents' ? 'menu-item-active' : 'menu-item-inactive'}`}
              onClick={() => setActiveSection('documents')}
            >
              Documents
            </button>
            <button className="btn-danger" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </div>
      </nav>

      {activeSection === 'chat' && (
        <>
          <div className="chat-container" ref={chatContainerRef}>
            {messages.map((message, index) => (
              <div
                key={index}
                className={message.isUser ? 'message-user' : 'message-bot'}
              >
                {message.text}
              </div>
            ))}
          </div>

          <div className="chat-input-container">
            <input
              className="input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !sending && sendMessage()}
              placeholder="Type your message..."
              disabled={sending || serverStatus === 'disconnected'}
            />
            <button
              className="btn-primary whitespace-nowrap"
              onClick={sendMessage}
              disabled={sending || serverStatus === 'disconnected'}
            >
              {sending ? 'Sending...' : 'Send'}
            </button>
          </div>
        </>
      )}

      {activeSection === 'documents' && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-bold mb-6">Document Management</h2>
          <div className="mb-6">
            <input
              type="file"
              onChange={handleFileUpload}
              className="hidden"
              id="file-upload"
              disabled={uploading}
            />
            <label
              htmlFor="file-upload"
              className="btn-primary inline-block cursor-pointer"
            >
              {uploading ? 'Uploading...' : 'Upload Document'}
            </label>
          </div>
          
          <div className="space-y-4">
            {documents.map((doc, index) => (
              <div
                key={index}
                className="flex justify-between items-center p-4 bg-gray-50 rounded-lg"
              >
                <span className="text-gray-700">{doc.filename}</span>
                <button
                  onClick={() => handleDeleteDocument(doc.id)}
                  className="btn-danger"
                >
                  Delete
                </button>
              </div>
            ))}
            {documents.length === 0 && (
              <p className="text-center text-gray-500">
                No documents uploaded yet
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
