import React, { useState, useEffect, useRef } from 'react';
import { API_BASE } from '../config';
import { Star, ChevronLeft, ChevronRight, Sparkles, Copy, Check, AlertCircle } from 'lucide-react';

export default function CustomerReview({ cardId, onBack }) {
  const [shop, setShop] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('carousel');
  const [customInput, setCustomInput] = useState('');
  const [customResult, setCustomResult] = useState('');
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState('');
  const [currentIdx, setCurrentIdx] = useState(0);

  const carouselRef = useRef(null);

  useEffect(() => {
    fetchReviews();
  }, [cardId]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  };

  const fetchReviews = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/reviews/${cardId}`);
      if (res.ok) {
        const data = await res.json();
        setShop(data.shop);
        setReviews(data.reviews || []);
      }
    } catch (err) {
      console.error(err);
      showToast('Could not load reviews');
    } finally {
      setLoading(false);
    }
  };

  const copyAndOpenGoogle = async (reviewText, reviewId = null) => {
    // 1. Copy to clipboard
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(reviewText);
      }
    } catch (e) {}

    // 2. Mark as used in DB
    if (reviewId) {
      fetch(`${API_BASE}/api/reviews/${reviewId}/use`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_id: cardId })
      }).catch(() => {});
    }

    showToast('✅ Review copied! Opening Google Review page...');

    // 3. Open Google review URL
    setTimeout(() => {
      const url = shop?.google_review_url || 'https://maps.google.com';
      window.open(url, '_blank');
    }, 400);
  };

  const handleGenerateCustom = async () => {
    if (!customInput.trim()) {
      showToast('Please type a short note first');
      return;
    }

    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/api/custom-review/${cardId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: customInput })
      });
      const data = await res.json();
      if (data.review) {
        setCustomResult(data.review);
      }
    } catch (err) {
      setCustomResult(`Had a wonderful experience at ${shop?.name || 'this shop'}! Highly recommended! ⭐⭐⭐⭐⭐`);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⚡</div>
          <div style={{ fontWeight: 700, color: '#0f172a' }}>Loading 5-Star Reviews...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div className="google-accent-bar" />

      <div style={{ width: '100%', maxWidth: 420, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 24, boxShadow: '0 20px 40px -15px rgba(15,23,42,0.1)', overflow: 'hidden' }}>
        {/* Store Title Header */}
        <div style={{ padding: '24px 20px 16px', textAlign: 'center', borderBottom: '1px solid #f1f5f9' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: '#eff6ff', padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 700, color: '#1d4ed8', marginBottom: 8 }}>
            <span>⭐ Official Google Feedback</span>
          </div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: '#0f172a', margin: 0 }}>
            {shop?.name || 'Store'}
          </h1>
          <p style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>
            Rate us 5 stars on Google Maps with 1 click
          </p>

          {/* Mode Switcher Tabs */}
          <div style={{ display: 'flex', background: '#f1f5f9', borderRadius: 12, padding: 3, marginTop: 16 }}>
            <button
              style={{ flex: 1, padding: '8px 12px', border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: 'pointer', background: activeTab === 'carousel' ? '#fff' : 'transparent', color: activeTab === 'carousel' ? '#0f172a' : '#64748b', boxShadow: activeTab === 'carousel' ? '0 2px 4px rgba(0,0,0,0.06)' : 'none' }}
              onClick={() => setActiveTab('carousel')}
            >
              ⭐ Pick a Review
            </button>
            <button
              style={{ flex: 1, padding: '8px 12px', border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: 'pointer', background: activeTab === 'custom' ? '#fff' : 'transparent', color: activeTab === 'custom' ? '#0f172a' : '#64748b', boxShadow: activeTab === 'custom' ? '0 2px 4px rgba(0,0,0,0.06)' : 'none' }}
              onClick={() => setActiveTab('custom')}
            >
              ✨ Write Your Own
            </button>
          </div>
        </div>

        {/* Content Section */}
        <div style={{ padding: 20 }}>
          {activeTab === 'carousel' ? (
            /* ── Carousel View ── */
            <div>
              {reviews.length > 0 ? (
                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 16, padding: '20px 18px', textAlign: 'center', minHeight: 180, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 4, color: '#fbbc04', marginBottom: 12 }}>
                    {[...Array(5)].map((_, i) => <Star key={i} size={20} fill="#fbbc04" />)}
                  </div>
                  <p style={{ fontSize: 15, fontWeight: 600, color: '#1e293b', fontStyle: 'italic', lineHeight: 1.5, margin: 0 }}>
                    "{reviews[currentIdx]?.content}"
                  </p>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', marginTop: 12 }}>
                    Card {currentIdx + 1} of {reviews.length}
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 30, color: '#64748b' }}>Generating fresh reviews...</div>
              )}

              {/* Navigation Arrows */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
                <button 
                  className="btn-secondary" 
                  style={{ padding: '8px 12px' }}
                  onClick={() => setCurrentIdx(prev => (prev === 0 ? reviews.length - 1 : prev - 1))}
                >
                  <ChevronLeft size={16} /> Previous
                </button>
                <div style={{ display: 'flex', gap: 6 }}>
                  {reviews.map((_, i) => (
                    <span 
                      key={i} 
                      style={{ width: 8, height: 8, borderRadius: '50%', background: i === currentIdx ? '#1a73e8' : '#cbd5e1', cursor: 'pointer' }}
                      onClick={() => setCurrentIdx(i)}
                    />
                  ))}
                </div>
                <button 
                  className="btn-secondary" 
                  style={{ padding: '8px 12px' }}
                  onClick={() => setCurrentIdx(prev => (prev === reviews.length - 1 ? 0 : prev + 1))}
                >
                  Next <ChevronRight size={16} />
                </button>
              </div>

              {/* Main Post Button */}
              <button 
                className="btn-primary" 
                style={{ width: '100%', marginTop: 20, padding: 14, fontSize: 15, justifyContent: 'center' }}
                onClick={() => copyAndOpenGoogle(reviews[currentIdx]?.content, reviews[currentIdx]?.id)}
              >
                Post Review on Google ↗
              </button>
            </div>
          ) : (
            /* ── Write Your Own / LangChain Expand Tab ── */
            <div>
              <p style={{ fontSize: 13, color: '#475569', marginBottom: 10 }}>
                Tell us what you liked (product, service, staff) and AI will polish it into a 5-star review!
              </p>
              <textarea
                style={{ width: '100%', minHeight: 90, padding: 12, borderRadius: 12, border: '1px solid #cbd5e1', fontSize: 14, outline: 'none', resize: 'vertical' }}
                placeholder="e.g. loved the helpful owner, clean place, and fast service..."
                value={customInput}
                onChange={e => setCustomInput(e.target.value)}
              />
              <button 
                className="btn-primary" 
                style={{ width: '100%', marginTop: 10, padding: 12, justifyContent: 'center' }}
                onClick={handleGenerateCustom}
                disabled={generating}
              >
                <Sparkles size={16} /> {generating ? 'Generating via LangChain...' : 'Generate 5★ Review'}
              </button>

              {customResult && (
                <div style={{ marginTop: 16, background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 12, padding: 14 }}>
                  <div style={{ display: 'flex', gap: 4, color: '#fbbc04', marginBottom: 8 }}>
                    {[...Array(5)].map((_, i) => <Star key={i} size={16} fill="#fbbc04" />)}
                  </div>
                  <p style={{ fontSize: 14, color: '#14532d', fontWeight: 600, margin: '0 0 12px 0' }}>
                    "{customResult}"
                  </p>
                  <button 
                    className="btn-primary" 
                    style={{ width: '100%', padding: 10, background: '#16a34a', justifyContent: 'center' }}
                    onClick={() => copyAndOpenGoogle(customResult)}
                  >
                    Post on Google ↗
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {onBack && (
          <div style={{ padding: '12px 20px', background: '#f8fafc', borderTop: '1px solid #f1f5f9', textAlign: 'center' }}>
            <button style={{ border: 'none', background: 'transparent', color: '#64748b', fontSize: 13, cursor: 'pointer', fontWeight: 600 }} onClick={onBack}>
              ← Return to Admin Panel
            </button>
          </div>
        )}
      </div>

      {toast && (
        <div style={{ position: 'fixed', bottom: 24, background: '#0f172a', color: '#fff', padding: '10px 22px', borderRadius: 30, fontSize: 13, fontWeight: 700, zIndex: 2000 }}>
          {toast}
        </div>
      )}
    </div>
  );
}
