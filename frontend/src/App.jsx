import React, { useState, useEffect } from 'react';
import AdminDashboard from './components/AdminDashboard';
import CustomerReview from './components/CustomerReview';

export default function App() {
  const [currentView, setCurrentView] = useState('admin');
  const [viewCardId, setViewCardId] = useState(null);

  useEffect(() => {
    // Parse initial route
    parseRoute();

    // Listen for browser / hardware back buttons
    const handlePopState = () => parseRoute();
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const parseRoute = () => {
    const path = window.location.pathname;
    const searchParams = new URLSearchParams(window.location.search);
    const hash = window.location.hash;

    // Check /r/:cardId
    if (path.startsWith('/r/')) {
      const card = path.replace('/r/', '').split('/')[0];
      if (card) {
        setViewCardId(card);
        setCurrentView('review');
        return;
      }
    }

    // Check ?card=:cardId
    if (searchParams.get('card')) {
      setViewCardId(searchParams.get('card'));
      setCurrentView('review');
      return;
    }

    // Check #r-:cardId
    if (hash.startsWith('#r-')) {
      const card = hash.replace('#r-', '');
      if (card) {
        setViewCardId(card);
        setCurrentView('review');
        return;
      }
    }

    setCurrentView('admin');
    setViewCardId(null);
  };

  const handleOpenReview = (cardId) => {
    setViewCardId(cardId);
    setCurrentView('review');
    window.history.pushState({}, '', `?card=${encodeURIComponent(cardId)}`);
  };

  const handleBackToAdmin = () => {
    setCurrentView('admin');
    setViewCardId(null);
    window.history.pushState({}, '', '/');
  };

  if (currentView === 'review' && viewCardId) {
    return <CustomerReview cardId={viewCardId} onBack={handleBackToAdmin} />;
  }

  return <AdminDashboard onOpenCard={handleOpenReview} />;
}
