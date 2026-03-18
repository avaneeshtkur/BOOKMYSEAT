/**
 * trailer.bundle.js
 * Clean and minimal YouTube embedding system (resolves Error 153).
 */

(function () {
  'use strict';

  // ── Utils: youtubeParser ──────────────────────────────────────────────────
  function extractYouTubeVideoId(url) {
    if (!url || typeof url !== 'string') return null;
    const regex = /^[a-zA-Z0-9_-]{11}$/;
    try {
      const urlObj = new URL(url);
      if (urlObj.hostname === 'youtu.be') {
        const id = urlObj.pathname.slice(1).split('/')[0];
        return regex.test(id) ? id : null;
      }
      if (urlObj.hostname.includes('youtube.com')) {
        const v = urlObj.searchParams.get('v');
        if (v && regex.test(v)) return v;

        if (urlObj.pathname.startsWith('/embed/')) {
          const id = urlObj.pathname.split('/embed/')[1];
          return regex.test(id) ? id : null;
        }
      }
    } catch (e) {
      if (regex.test(url)) return url;
    }
    return null;
  }

  function buildEmbedUrl(videoId) {
    if (!videoId || !/^[a-zA-Z0-9_-]{11}$/.test(videoId)) return null;
    return `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1&controls=1&rel=0`;
  }

  // ── Component: trailerModal ───────────────────────────────────────────────
  let modalOverlay = null;
  let modalVideoWrap = null;

  function createModal() {
    if (modalOverlay) return;
    modalOverlay = document.createElement('div');
    modalOverlay.id = 'trailer-modal';

    const box = document.createElement('div');
    box.className = 'tm-box';
    const closeBtn = document.createElement('button');
    closeBtn.className = 'tm-close';
    closeBtn.textContent = '✕';
    closeBtn.onclick = closeModal;

    modalVideoWrap = document.createElement('div');
    modalVideoWrap.className = 'tm-video';

    box.appendChild(closeBtn);
    box.appendChild(modalVideoWrap);
    modalOverlay.appendChild(box);
    document.body.appendChild(modalOverlay);

    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeModal();
    });
  }

  function openModal(rawUrl) {
    createModal();
    modalVideoWrap.innerHTML = '';
    const videoId = extractYouTubeVideoId(rawUrl);
    if (!videoId) {
      const errorMsg = document.createElement('p');
      errorMsg.className = 'trailer-unavailable';
      errorMsg.textContent = 'Trailer unavailable';
      modalVideoWrap.appendChild(errorMsg);
    } else {
      const iframe = document.createElement('iframe');
      iframe.src = buildEmbedUrl(videoId);
      iframe.setAttribute('frameborder', '0');
      iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
      iframe.setAttribute('allowfullscreen', '');
      modalVideoWrap.appendChild(iframe);
    }
    modalOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    if (modalOverlay) {
      modalOverlay.classList.remove('active');
      modalVideoWrap.innerHTML = '';
    }
    document.body.style.overflow = '';
  }

  // ── Component: trailerPreview (Hover effects for cards) ───────────────────
  function setupTrailerPreview(card) {
    const rawUrl = card.dataset.trailerUrl;
    const container = card.querySelector('.trailer-preview-container');
    if (!container || !rawUrl) return;

    const videoId = extractYouTubeVideoId(rawUrl);
    if (!videoId) {
      const errorMsg = document.createElement('p');
      errorMsg.className = 'trailer-unavailable';
      errorMsg.textContent = 'Trailer unavailable';
      container.appendChild(errorMsg);
      return;
    }

    const embedUrl = buildEmbedUrl(videoId);
    if (!embedUrl) return;

    let hoverTimer = null;

    card.addEventListener('mouseenter', () => {
      hoverTimer = setTimeout(() => {
        container.innerHTML = '';
        const iframe = document.createElement('iframe');
        iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1&controls=0&rel=0&playsinline=1`;
        iframe.setAttribute('frameborder', '0');
        iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
        iframe.setAttribute('allowfullscreen', 'true');
        container.appendChild(iframe);
        
        // Trigger CSS transition smoothly
        requestAnimationFrame(() => container.classList.add('visible'));
      }, 400); // Wait 400ms before starting preview
    });

    card.addEventListener('mouseleave', () => {
      clearTimeout(hoverTimer);
      container.classList.remove('visible');
      // Resource Cleanup: Destroy iframe
      container.innerHTML = '';
    });

    card.addEventListener('click', (e) => {
      if (e.target.closest('a') || e.target.closest('button')) return;
      openModal(rawUrl);
    });
  }

  function initPreviews() {
    const cards = document.querySelectorAll('.movie-card[data-trailer-url]');
    if (!cards.length) return;

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            setupTrailerPreview(entry.target);
            obs.unobserve(entry.target);
          }
        });
      }, { rootMargin: '200px' });
      
      cards.forEach(card => observer.observe(card));
    } else {
      cards.forEach(setupTrailerPreview);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initPreviews();
  });

})();
