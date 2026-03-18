/**
 * trailerPreview.js
 */
import { extractYouTubeVideoId, buildEmbedUrl } from '../utils/youtubeParser.js';

export function setupTrailerPreview(card) {
  const rawUrl = card.dataset.trailerUrl;
  const container = card.querySelector('.trailer-preview-container');
  if (!container || !rawUrl) return;

  const videoId = extractYouTubeVideoId(rawUrl);
  
  if (!videoId) {
    const errorMsg = document.createElement('p');
    errorMsg.className = 'trailer-unavailable';
    errorMsg.textContent = 'Trailer unavailable';
    container.appendChild(errorMsg);
    // Even if invalid, add it to DOM so hover shows unavailable
    return;
  }

  const embedUrl = buildEmbedUrl(videoId);
  if (!embedUrl) return;

  let hoverTimer = null;
  let iframeCreated = false;

  card.addEventListener('mouseenter', () => {
    hoverTimer = setTimeout(() => {
      if (!iframeCreated) {
        container.innerHTML = '';
        const iframe = document.createElement('iframe');
        iframe.src = embedUrl;
        iframe.setAttribute('frameborder', '0');
        iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
        iframe.setAttribute('allowfullscreen', '');
        container.appendChild(iframe);
        iframeCreated = true;
      }
      container.classList.add('visible');
    }, 500);
  });

  card.addEventListener('mouseleave', () => {
    clearTimeout(hoverTimer);
    container.classList.remove('visible');
  });
}

function initPreviews() {
  const cards = document.querySelectorAll('[data-trailer-url]');
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

document.addEventListener('DOMContentLoaded', initPreviews);
