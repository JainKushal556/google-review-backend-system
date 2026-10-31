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
    <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '16px 14px' }}>
      <div className="google-accent-bar" />

      <div style={{ width: '100%', maxWidth: 410, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 24, boxShadow: '0 16px 36px -10px rgba(15,23,42,0.08)', overflow: 'hidden' }}>
        
        {/* Clean Header: Focused on Shop Name only */}
        <div style={{ padding: '24px 20px 14px', textAlign: 'center' }}>
          <h1 style={{ fontSize: 21, fontWeight: 800, color: '#0f172a', margin: 0, letterSpacing: '-0.3px' }}>
            {shop?.name || 'Store'}
          </h1>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 3, color: '#fbbc04', marginTop: 8 }}>
            {[...Array(5)].map((_, i) => <Star key={i} size={19} fill="#fbbc04" />)}
          </div>

          {/* Minimal Mode Tabs */}
          <div style={{ display: 'flex', background: '#f1f5f9', borderRadius: 10, padding: 3, marginTop: 16 }}>
            <button
              style={{ flex: 1, padding: '7px 10px', border: 'none', borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: 'pointer', background: activeTab === 'carousel' ? '#fff' : 'transparent', color: activeTab === 'carousel' ? '#0f172a' : '#64748b', boxShadow: activeTab === 'carousel' ? '0 1px 3px rgba(0,0,0,0.06)' : 'none' }}
              onClick={() => setActiveTab('carousel')}
            >
              Select Review
            </button>
            <button
              style={{ flex: 1, padding: '7px 10px', border: 'none', borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: 'pointer', background: activeTab === 'custom' ? '#fff' : 'transparent', color: activeTab === 'custom' ? '#0f172a' : '#64748b', boxShadow: activeTab === 'custom' ? '0 1px 3px rgba(0,0,0,0.06)' : 'none' }}
              onClick={() => setActiveTab('custom')}
            >
              Custom Note
            </button>
          </div>
        </div>

        {/* Focused Content Area */}
        <div style={{ padding: '0 20px 22px' }}>
          {activeTab === 'carousel' ? (
            /* ── Swipeable Native Touch Carousel ── */
            <div>
              {reviews.length > 0 ? (
                <div>
                  {/* Horizontal Scroll Track with Native Snap */}
                  <div 
                    ref={carouselRef}
                    onScroll={(e) => {
                      const scrollLeft = e.target.scrollLeft;
                      const width = e.target.clientWidth;
                      if (width > 0) {
                        const newIndex = Math.round(scrollLeft / width);
                        if (newIndex !== currentIdx && newIndex >= 0 && newIndex < reviews.length) {
                          setCurrentIdx(newIndex);
                        }
                      }
                    }}
                    style={{ 
                      display: 'flex', 
                      overflowX: 'auto', 
                      scrollSnapType: 'x mandatory', 
                      scrollbarWidth: 'none', 
                      msOverflowStyle: 'none',
                      WebkitOverflowScrolling: 'touch',
                      gap: 12,
                      padding: '4px 2px',
                      cursor: 'grab'
                    }}
                  >
                    {reviews.map((rev, idx) => (
                      <div 
                        key={rev.id || idx}
                        style={{ 
                          flex: '0 0 100%', 
                          scrollSnapAlign: 'center', 
                          background: '#ffffff', 
                          border: '1.5px solid #e2e8f0', 
                          borderRadius: 20, 
                          padding: '24px 20px', 
                          textAlign: 'center', 
                          minHeight: 140, 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'center',
                          boxShadow: '0 4px 16px rgba(0,0,0,0.03)',
                          userSelect: 'none'
                        }}
                      >
                        <p style={{ 
                          fontSize: 16.5, 
                          fontWeight: 600, 
                          color: '#0f172a', 
                          lineHeight: 1.55, 
                          margin: 0,
                          wordBreak: 'break-word'
                        }}>
                          "{rev.content}"
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Clean Dot Indicators (Live Sync with swipe) */}
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 6, marginTop: 14 }}>
                    {reviews.map((_, i) => (
                      <span 
                        key={i} 
                        style={{ 
                          width: i === currentIdx ? 20 : 6, 
                          height: 6, 
                          borderRadius: 4, 
                          background: i === currentIdx ? '#1a73e8' : '#cbd5e1', 
                          cursor: 'pointer',
                          transition: 'all 0.25s ease'
                        }}
                        onClick={() => {
                          setCurrentIdx(i);
                          if (carouselRef.current) {
                            carouselRef.current.scrollTo({
                              left: i * carouselRef.current.clientWidth,
                              behavior: 'smooth'
                            });
                          }
                        }}
                      />
                    ))}
                  </div>

                  <div style={{ textAlign: 'center', fontSize: 11.5, color: '#94a3b8', marginTop: 6, fontWeight: 600 }}>
                    👈 Swipe left or right 👉
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 30, color: '#64748b' }}>Loading reviews...</div>
              )}

              {/* Main Action Button */}
              <button 
                className="btn-primary" 
                style={{ width: '100%', marginTop: 16, padding: 13, fontSize: 15, fontWeight: 700, borderRadius: 12, justifyContent: 'center' }}
                onClick={() => copyAndOpenGoogle(reviews[currentIdx]?.content, reviews[currentIdx]?.id)}
              >
                Post on Google ↗
              </button>
            </div>
          ) : (
            /* ── Clean Custom Note Tab ── */
            <div>
              <textarea
                style={{ 
                  width: '100%', 
                  minHeight: 85, 
                  padding: 12, 
                  borderRadius: 12, 
                  border: '1.5px solid #cbd5e1', 
                  fontSize: 14, 
                  outline: 'none', 
                  resize: 'none',
                  fontFamily: 'inherit'
                }}
                placeholder="What did you like? (e.g. good service, polite staff)..."
                value={customInput}
                onChange={e => setCustomInput(e.target.value)}
              />
              <button 
                className="btn-primary" 
                style={{ width: '100%', marginTop: 10, padding: 12, fontSize: 14, borderRadius: 12, justifyContent: 'center' }}
                onClick={handleGenerateCustom}
                disabled={generating}
              >
                <Sparkles size={16} /> {generating ? 'Crafting Review...' : 'Generate 5★ Review'}
              </button>

              {customResult && (
                <div style={{ marginTop: 14, background: '#f8fafc', border: '1.5px solid #86efac', borderRadius: 14, padding: 16 }}>
                  <p style={{ fontSize: 15, color: '#0f172a', fontWeight: 600, margin: '0 0 12px 0', lineHeight: 1.5 }}>
                    "{customResult}"
                  </p>
                  <button 
                    className="btn-primary" 
                    style={{ width: '100%', padding: 11, background: '#16a34a', borderRadius: 10, justifyContent: 'center', fontSize: 14 }}
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
          <div style={{ padding: '10px 16px', background: '#f8fafc', borderTop: '1px solid #f1f5f9', textAlign: 'center' }}>
            <button style={{ border: 'none', background: 'transparent', color: '#94a3b8', fontSize: 12, cursor: 'pointer', fontWeight: 600 }} onClick={onBack}>
              ← Back to Admin
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
