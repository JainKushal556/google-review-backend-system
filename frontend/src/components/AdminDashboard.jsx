import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';
import { 
  CreditCard, Search, Plus, ExternalLink, Copy, Check, 
  Trash2, RefreshCw, ArrowLeft, Store, Sparkles, AlertCircle, Play, Pause,
  Lock, LogOut, ShieldCheck
} from 'lucide-react';

export default function AdminDashboard({ onOpenCard }) {
  const [token, setToken] = useState(localStorage.getItem('nfc_admin_token') || '');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);

  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [selectedCard, setSelectedCard] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState('');

  // Form states
  const [cardId, setCardId] = useState('');
  const [reviewUrl, setReviewUrl] = useState('');
  const [shopName, setShopName] = useState('');
  const [shopType, setShopType] = useState('Other');
  const [description, setDescription] = useState('');
  const [keywords, setKeywords] = useState([]);
  const [detecting, setDetecting] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    verifySession();
  }, []);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  };

  const getAuthHeaders = () => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  });

  const verifySession = async () => {
    const savedToken = localStorage.getItem('nfc_admin_token');
    if (!savedToken) {
      setCheckingAuth(false);
      setIsAuthenticated(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/admin/verify`, {
        headers: { 'Authorization': `Bearer ${savedToken}` }
      });
      if (res.ok) {
        setToken(savedToken);
        setIsAuthenticated(true);
        loadCards(savedToken);
      } else {
        handleLogout();
      }
    } catch (err) {
      handleLogout();
    } finally {
      setCheckingAuth(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!loginPassword.trim()) return;

    setLoggingIn(true);
    setLoginError('');

    try {
      const res = await fetch(`${API_BASE}/api/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: loginPassword.trim() })
      });
      const data = await res.json();

      if (res.ok && data.token) {
        localStorage.setItem('nfc_admin_token', data.token);
        setToken(data.token);
        setIsAuthenticated(true);
        setLoginPassword('');
        showToast('✅ Login Successful! Welcome Admin.');
        loadCards(data.token);
      } else {
        setLoginError(data.detail || 'Incorrect admin password');
      }
    } catch (err) {
      setLoginError('Could not connect to backend server');
    } finally {
      setLoggingIn(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('nfc_admin_token');
    setToken('');
    setIsAuthenticated(false);
    setCards([]);
    setSelectedCard(null);
  };

  const loadCards = async (activeToken = token) => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/cards`, {
        headers: {
          'Authorization': `Bearer ${activeToken}`
        }
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setCards(data);
      }
    } catch (err) {
      console.error(err);
      showToast('⚠️ Could not connect to backend');
    } finally {
      setLoading(false);
    }
  };

  // Smart Detect via LangChain
  const handleUrlChange = async (url) => {
    setReviewUrl(url);
    if (!url || url.length < 10) return;

    setDetecting(true);
    try {
      const res = await fetch(`${API_BASE}/api/smart-detect`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ url, shop_name: shopName })
      });
      const data = await res.json();
      if (data.review_url) setReviewUrl(data.review_url);
      if (data.shop_name && !shopName) setShopName(data.shop_name);
      if (data.suggested_card_id && !cardId) setCardId(data.suggested_card_id);
      if (data.shop_type) setShopType(data.shop_type);
      if (data.description && !description) setDescription(data.description);
      if (data.keywords && data.keywords.length > 0 && keywords.length === 0) setKeywords(data.keywords);
    } catch (err) {
      console.error("Smart detect failed:", err);
    } finally {
      setDetecting(false);
    }
  };

  const handleSaveCard = async (e) => {
    e.preventDefault();
    if (!reviewUrl) {
      showToast('Please enter Google Review URL');
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/cards`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          card_id: cardId,
          google_review_url: reviewUrl,
          shop_name: shopName || 'My Store',
          shop_type: shopType,
          description,
          keywords
        })
      });

      const data = await res.json();
      if (res.ok) {
        showToast('✅ Card created & LangChain pre-generation started!');
        setModalOpen(false);
        resetForm();
        loadCards();
      } else {
        showToast(data.detail || data.error || 'Failed to save card');
      }
    } catch (err) {
      showToast('Network error while saving');
    } finally {
      setSaving(false);
    }
  };

  const toggleStatus = async (targetCardId, e) => {
    if (e) e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/api/cards/${targetCardId}/toggle-status`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.is_active ? '✅ NFC Card is now LIVE' : '⏸️ NFC Card service PAUSED');
        loadCards();
        if (selectedCard && selectedCard.card_id === targetCardId) {
          setSelectedCard(prev => ({ ...prev, is_active: data.is_active }));
        }
      }
    } catch (err) {
      showToast('Failed to toggle status');
    }
  };

  const deleteCard = async (targetCardId, e) => {
    if (e) e.stopPropagation();
    if (!window.confirm(`Delete card "${targetCardId}"?`)) return;
    try {
      await fetch(`${API_BASE}/api/cards/${targetCardId}`, { 
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      showToast('Card deleted');
      setSelectedCard(null);
      loadCards();
    } catch (err) {
      showToast('Failed to delete card');
    }
  };

  const resetForm = () => {
    setCardId('');
    setReviewUrl('');
    setShopName('');
    setShopType('Other');
    setDescription('');
    setKeywords([]);
  };

  // If checking authentication
  if (checkingAuth) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🔒</div>
          <div style={{ fontWeight: 700, color: '#0f172a' }}>Verifying Security Session...</div>
        </div>
      </div>
    );
  }

  // ── Admin Login Lock Screen ──
  if (!isAuthenticated) {
    return (
      <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
        <div className="google-accent-bar" />
        <div style={{ width: '100%', maxWidth: 400, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 24, boxShadow: '0 20px 40px -15px rgba(15,23,42,0.1)', padding: 32, textAlign: 'center' }}>
          <div style={{ width: 52, height: 52, background: '#eff6ff', borderRadius: 16, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: '#1a73e8', marginBottom: 16 }}>
            <Lock size={26} />
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 800, color: '#0f172a', marginBottom: 6 }}>Admin Dashboard</h2>
          <p style={{ fontSize: 13, color: '#64748b', marginBottom: 24 }}>Enter your secure admin password to manage NFC review cards.</p>

          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: 16, textAlign: 'left' }}>
              <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                Master Admin Password
              </label>
              <input
                type="password"
                className="search-input"
                style={{ paddingLeft: 14 }}
                placeholder="••••••••"
                value={loginPassword}
                onChange={e => setLoginPassword(e.target.value)}
                autoFocus
              />
            </div>

            {loginError && (
              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', fontSize: 13, fontWeight: 600, padding: '10px 14px', borderRadius: 10, marginBottom: 16 }}>
                {loginError}
              </div>
            )}

            <button type="submit" className="btn-primary" style={{ width: '100%', padding: 13, justifyContent: 'center' }} disabled={loggingIn}>
              <ShieldCheck size={18} /> {loggingIn ? 'Authenticating...' : 'Unlock Dashboard'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const filteredCards = cards.filter(c => {
    const matchesSearch = c.shop_name?.toLowerCase().includes(search.toLowerCase()) || 
                          c.card_id?.toLowerCase().includes(search.toLowerCase());
    if (filter === 'active') return matchesSearch && c.is_active !== false;
    if (filter === 'paused') return matchesSearch && c.is_active === false;
    return matchesSearch;
  });

  const totalScans = cards.reduce((acc, c) => acc + (c.scan_stats?.total || 0), 0);
  const activeCount = cards.filter(c => c.is_active !== false).length;

  return (
    <div>
      <div className="google-accent-bar" />

      {/* Desktop Sidebar */}
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-icon">
            <CreditCard size={22} color="#1a73e8" />
          </div>
          <div className="logo-text">
            NFC Review Cards
            <span>Smart Feedback OS</span>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="nav-link active">
            <Store size={18} /> Store Directory
          </div>
        </nav>

        {/* Bottom Logout */}
        <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--border)' }}>
          <button 
            style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', border: 'none', background: 'transparent', color: '#dc2626', fontSize: 13, fontWeight: 700, cursor: 'pointer', borderRadius: 8 }}
            onClick={handleLogout}
          >
            <LogOut size={16} /> Log Out
          </button>
        </div>
      </aside>

      {/* Mobile Top Header */}
      <header className="mobile-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="logo-icon" style={{ width: 34, height: 34 }}>
            <CreditCard size={18} color="#1a73e8" />
          </div>
          <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-heading)' }}>
            NFC Review Cards
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-primary" style={{ padding: '8px 12px', fontSize: 13 }} onClick={() => setModalOpen(true)}>
            <Plus size={16} /> Add
          </button>
          <button className="btn-secondary" style={{ padding: '8px 10px', color: '#dc2626' }} onClick={handleLogout} title="Log Out">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main">
        {selectedCard ? (
          /* ── Dedicated Card Details View ── */
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
              <button className="btn-secondary" onClick={() => setSelectedCard(null)}>
                <ArrowLeft size={16} /> Back to All Cards
              </button>
              <div style={{ fontSize: 13, color: 'var(--text-sub)' }}>
                Directory / <strong>{selectedCard.card_id}</strong>
              </div>
            </div>

            {/* Master Status Banner */}
            <div className={`master-status-card ${selectedCard.is_active !== false ? 'is-live' : 'is-paused'}`}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: selectedCard.is_active !== false ? '#15803d' : '#b91c1c' }}>
                  <span className="pulse-dot" />
                  {selectedCard.is_active !== false ? 'NFC SERVICE ACTIVE & LIVE' : 'NFC SERVICE PAUSED'}
                </div>
                <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-heading)', marginTop: 4 }}>
                  {selectedCard.is_active !== false ? 'Accepting Customer NFC Taps & Reviews' : 'Customer Tap Link Temporarily Disabled'}
                </div>
              </div>
              <button 
                className={`btn-primary`}
                style={{ background: selectedCard.is_active !== false ? '#dc2626' : '#16a34a' }}
                onClick={(e) => toggleStatus(selectedCard.card_id, e)}
              >
                {selectedCard.is_active !== false ? <><Pause size={16} /> Pause Service</> : <><Play size={16} /> Activate Service</>}
              </button>
            </div>

            {/* Store Profile Card */}
            <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 'var(--radius-xl)', padding: 24, marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <span className="smart-card-chip">ID: {selectedCard.card_id}</span>
                  <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', marginTop: 8 }}>
                    {selectedCard.shop_name}
                  </h1>
                  <p style={{ color: 'var(--text-sub)', fontSize: 14, marginTop: 4 }}>{selectedCard.description}</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn-secondary" onClick={() => onOpenCard(selectedCard.card_id)}>
                    <ExternalLink size={16} /> Open Review Page
                  </button>
                  <button className="btn-secondary" style={{ color: '#dc2626' }} onClick={(e) => deleteCard(selectedCard.card_id, e)}>
                    <Trash2 size={16} /> Delete
                  </button>
                </div>
              </div>
            </div>

            {/* Scan Metrics Grid */}
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{selectedCard.scan_stats?.today || 0}</div>
                <div className="stat-label">Scans Today</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{selectedCard.scan_stats?.month || 0}</div>
                <div className="stat-label">This Month</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{selectedCard.scan_stats?.total || 0}</div>
                <div className="stat-label">Lifetime Scans</div>
              </div>
            </div>
          </div>
        ) : (
          /* ── Overview List View ── */
          <div>
            <div className="page-header">
              <div>
                <h1 className="page-title">Google NFC Review Cards</h1>
                <p className="page-sub">FastAPI & LangChain Infrastructure for smart customer feedback.</p>
              </div>
              <button className="btn-primary" onClick={() => setModalOpen(true)}>
                <Plus size={18} /> Add New Card
              </button>
            </div>

            {/* Metrics */}
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon-wrap stat-icon-blue"><Store size={22} /></div>
                <div>
                  <div className="stat-value">{cards.length}</div>
                  <div className="stat-label">Total Store Cards</div>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon-wrap stat-icon-green"><Check size={22} /></div>
                <div>
                  <div className="stat-value">{activeCount}</div>
                  <div className="stat-label">Active & Live</div>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon-wrap stat-icon-amber"><CreditCard size={22} /></div>
                <div>
                  <div className="stat-value">{totalScans}</div>
                  <div className="stat-label">Total Lifetime Scans</div>
                </div>
              </div>
            </div>

            {/* Search & Filters */}
            <div className="toolbar-section">
              <div className="search-box-wrap">
                <Search className="search-icon" size={18} />
                <input 
                  className="search-input" 
                  placeholder="Search cards by name or ID..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="filter-pills-row">
                <button className={`filter-pill ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
                  All ({cards.length})
                </button>
                <button className={`filter-pill ${filter === 'active' ? 'active' : ''}`} onClick={() => setFilter('active')}>
                  ● Live ({activeCount})
                </button>
                <button className={`filter-pill ${filter === 'paused' ? 'active' : ''}`} onClick={() => setFilter('paused')}>
                  ○ Paused ({cards.length - activeCount})
                </button>
              </div>
            </div>

            {/* Cards Grid */}
            <div className="cards-showcase-grid">
              {filteredCards.map(card => (
                <div 
                  key={card.id || card.card_id} 
                  className="nfc-smart-card"
                  onClick={() => setSelectedCard(card)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="smart-card-chip">ID: {card.card_id}</span>
                    <span className={`smart-status-badge ${card.is_active !== false ? 'active' : 'inactive'}`}>
                      <span className="pulse-dot" />
                      {card.is_active !== false ? 'Active' : 'Paused'}
                    </span>
                  </div>

                  <h3 className="smart-shop-name">{card.shop_name}</h3>
                  <div style={{ fontSize: 13, color: 'var(--text-sub)', marginTop: 2 }}>{card.shop_type || 'Store'}</div>

                  <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: 12.5, color: 'var(--text-sub)' }}>
                      <strong>{card.scan_stats?.total || 0}</strong> Lifetime Scans
                    </div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--google-blue)' }}>
                      Manage →
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* ── Add Card Modal ── */}
      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-heading)', marginBottom: 8 }}>
              ⚡ Configure NFC Review Card
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 20 }}>
              AI powered by LangChain will automatically analyze Google Maps link and generate 10 natural reviews.
            </p>

            <form onSubmit={handleSaveCard}>
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                  1. Printed Card ID
                </label>
                <input 
                  className="search-input" 
                  style={{ paddingLeft: 14 }}
                  placeholder="e.g. CARD-01, SHOP-101, or brand-name"
                  value={cardId}
                  onChange={e => setCardId(e.target.value)}
                />
              </div>

              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                  2. Google Review Destination URL *
                </label>
                <input 
                  className="search-input" 
                  style={{ paddingLeft: 14 }}
                  placeholder="https://maps.app.goo.gl/... or review link"
                  value={reviewUrl}
                  onChange={e => handleUrlChange(e.target.value)}
                />
                {detecting && (
                  <div style={{ fontSize: 12, color: 'var(--google-blue)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Sparkles size={14} /> LangChain analyzing business profile...
                  </div>
                )}
              </div>

              <div style={{ marginBottom: 20 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                  3. Business / Store Name
                </label>
                <input 
                  className="search-input" 
                  style={{ paddingLeft: 14 }}
                  placeholder="e.g. Dream Art Tattoo Studio"
                  value={shopName}
                  onChange={e => setShopName(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? 'Saving...' : '💾 Save & Generate Card'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {toast && (
        <div style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', background: '#0f172a', color: '#fff', padding: '10px 20px', borderRadius: 30, fontSize: 13, fontWeight: 700, zIndex: 2000 }}>
          {toast}
        </div>
      )}
    </div>
  );
}
