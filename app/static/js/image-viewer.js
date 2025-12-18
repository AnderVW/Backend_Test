/**
 * Image Viewer - Lightbox functionality for viewing images in full size
 * Usage: Add class 'image-viewer-trigger' to any image element
 */

(function() {
    'use strict';

    let currentImageSrc = '';
    let viewer = null;

    // Initialize viewer
    function init() {
        createViewer();
        attachEventListeners();
    }

    // Create viewer HTML structure
    function createViewer() {
        viewer = document.createElement('div');
        viewer.id = 'imageViewer';
        viewer.className = 'fixed inset-0 z-[100] hidden items-center justify-center bg-black bg-opacity-90 backdrop-blur-sm';
        viewer.style.display = 'none';
        
        viewer.innerHTML = `
            <button id="closeImageViewer" class="absolute top-4 right-4 p-2 text-white hover:bg-white hover:bg-opacity-20 rounded-lg transition-colors z-10">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
            <div id="imageViewerContent" class="w-full h-full p-4 flex items-center justify-center">
                <img id="viewerImage" alt="Full size image" class="max-w-full max-h-[90vh] w-auto h-auto object-contain rounded-lg shadow-2xl" style="display: none;">
            </div>
            <div id="imageViewerLoading" class="absolute inset-0 flex items-center justify-center" style="display: none;">
                <div class="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-white border-r-transparent"></div>
            </div>
        `;
        
        document.body.appendChild(viewer);
    }

    // Attach event listeners
    function attachEventListeners() {
        // Close button
        document.getElementById('closeImageViewer').addEventListener('click', closeViewer);
        
        // Click outside image to close
        viewer.addEventListener('click', function(e) {
            if (e.target === viewer || e.target.id === 'imageViewerContent') {
                closeViewer();
            }
        });
        
        // ESC key to close
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && viewer.style.display === 'flex') {
                closeViewer();
            }
        });
        
        // Image loaded
        const viewerImage = document.getElementById('viewerImage');
        viewerImage.addEventListener('load', function() {
            if (this.src && this.src !== window.location.href) {
                document.getElementById('imageViewerLoading').style.display = 'none';
                this.style.display = 'block';
            }
        });
        
        // Image error
        viewerImage.addEventListener('error', function() {
            // Only show error if we actually tried to load an image
            if (this.src && this.src !== window.location.href && this.src !== '') {
                document.getElementById('imageViewerLoading').style.display = 'none';
                alert('Failed to load image');
                closeViewer();
            }
        });
    }

    // Open viewer with image
    function openViewer(imageSrc) {
        if (!imageSrc || imageSrc === '') return;
        
        currentImageSrc = imageSrc;
        
        // Show loading
        const loadingEl = document.getElementById('imageViewerLoading');
        const viewerImage = document.getElementById('viewerImage');
        
        loadingEl.style.display = 'flex';
        viewerImage.style.display = 'none';
        
        // Set image
        viewerImage.src = imageSrc;
        
        // Show viewer
        viewer.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    // Close viewer
    function closeViewer() {
        viewer.style.display = 'none';
        document.body.style.overflow = '';
        
        // Clear image
        const viewerImage = document.getElementById('viewerImage');
        viewerImage.style.display = 'none';
        viewerImage.src = '';
        
        currentImageSrc = '';
    }

    // Make images clickable
    window.makeImageViewable = function(imageElement) {
        if (!imageElement) return;
        
        imageElement.style.cursor = 'pointer';
        imageElement.classList.add('image-viewer-trigger');
        
        // Remove existing listener if any
        const newElement = imageElement.cloneNode(true);
        imageElement.parentNode.replaceChild(newElement, imageElement);
        
        // Add click listener
        newElement.addEventListener('click', function(e) {
            e.stopPropagation();
            const imgSrc = this.src || this.dataset.fullSrc;
            if (imgSrc) {
                openViewer(imgSrc);
            }
        });
        
        return newElement;
    };

    // Auto-attach to all images with class 'image-viewer-trigger'
    function autoAttach() {
        const images = document.querySelectorAll('img.image-viewer-trigger:not([data-viewer-attached])');
        images.forEach(img => {
            img.style.cursor = 'pointer';
            img.dataset.viewerAttached = 'true';
            
            img.addEventListener('click', function(e) {
                e.stopPropagation();
                const imgSrc = this.src || this.dataset.fullSrc;
                if (imgSrc) {
                    openViewer(imgSrc);
                }
            });
        });
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            init();
            autoAttach();
        });
    } else {
        init();
        autoAttach();
    }

    // Expose autoAttach for dynamically loaded content
    window.imageViewerAutoAttach = autoAttach;

})();

