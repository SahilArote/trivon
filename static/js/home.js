
	document.addEventListener('DOMContentLoaded', function() {
		const slidesContainer = document.getElementById('slidesContainer');
		const dotsContainer = document.getElementById('slideDots');
		const bannerSlider = document.querySelector('.banner-slider');
		const slides = document.querySelectorAll('.slide');
		let currentSlide = 0;
		let autoSlideInterval;
		let isTransitioning = false;
		let startX = 0;
		let currentX = 0;
		let isDragging = false;
		
		// Create dots
		slides.forEach((_, index) => {
			const dot = document.createElement('div');
			dot.classList.add('dot');
			if (index === 0) dot.classList.add('active');
			dot.addEventListener('click', () => goToSlide(index));
			dotsContainer.appendChild(dot);
		});
		
		const dots = document.querySelectorAll('.dot');
		
		function showSlide(n) {
			// Ensure n is within bounds
			n = n % slides.length;
			currentSlide = n;
			
			// Update dots
			dots.forEach((dot, index) => {
				dot.classList.toggle('active', index === n);
			});
			
			// Use transform for smooth animation
			slidesContainer.style.transform = `translateX(-${n * 100}%)`;
		}
		
		function nextSlide() {
		showSlide(currentSlide + 1);
	}
	
	function prevSlide() {
		showSlide(currentSlide - 1 < 0 ? slides.length - 1 : currentSlide - 1);
	}
	
	function goToSlide(n) {
		currentSlide = n;
		clearInterval(autoSlideInterval);
		showSlide(currentSlide);
		startAutoSlide();
	}
	
	function startAutoSlide() {
		autoSlideInterval = setInterval(nextSlide, 5000); // Change every 5 seconds
	}
	
	// Touch/Mouse events for swiping
	bannerSlider.addEventListener('mousedown', handleDragStart, false);
	bannerSlider.addEventListener('touchstart', handleDragStart, false);
	
	bannerSlider.addEventListener('mousemove', handleDragMove, false);
	bannerSlider.addEventListener('touchmove', handleDragMove, false);
	
	bannerSlider.addEventListener('mouseup', handleDragEnd, false);
	bannerSlider.addEventListener('touchend', handleDragEnd, false);
	bannerSlider.addEventListener('mouseleave', handleDragEnd, false);
	
	function handleDragStart(e) {
		isDragging = true;
		startX = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
		clearInterval(autoSlideInterval);
	}
	
	function handleDragMove(e) {
		if (!isDragging) return;
		currentX = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
	}
	
	function handleDragEnd(e) {
		if (!isDragging) return;
		isDragging = false;
		
		const diff = startX - currentX;
		const threshold = 50; // Minimum drag distance
		
		if (Math.abs(diff) > threshold) {
			if (diff > 0) {
				// Swiped left, go to next slide
				nextSlide();
			} else {
				// Swiped right, go to previous slide
				prevSlide();
			}
		}
		
		startAutoSlide();
	}
	
	// Initialize
	showSlide(0);
	startAutoSlide();
});
