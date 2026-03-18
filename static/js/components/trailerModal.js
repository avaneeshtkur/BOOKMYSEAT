/**
 * trailerModal.js
 */
import { extractYouTubeVideoId, buildEmbedUrl } from '../utils/youtubeParser.js';

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

export function openModal(rawUrl) {
  createModal();
  modalVideoWrap.innerHTML = '';

  const videoId = extractYouTubeVideoId(rawUrl);
  if (!videoId) {
    const errorMsg = document.createElement('p');
    errorMsg.className = 'trailer-unavailable';
    errorMsg.textContent = 'Trailer unavailable';
    modalVideoWrap.appendChild(errorMsg);
  } else {
    const embedUrl = buildEmbedUrl(videoId);
    const iframe = document.createElement('iframe');
    iframe.src = embedUrl;
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

function initModals() {
  const cards = document.querySelectorAll('[data-trailer-url]');
  cards.forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('a') || e.target.closest('button')) return;
      const url = card.dataset.trailerUrl;
      if (url) openModal(url);
    });
  });
}

document.addEventListener('DOMContentLoaded', initModals);
