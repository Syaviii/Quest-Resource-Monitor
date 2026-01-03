/**
 * VR System Monitor - Animation Helpers
 * CSS and JS animation utilities
 */

const Animations = (function() {
    
    /**
     * Fade an element in
     */
    function fadeIn(element, duration = 200) {
        if (!element) return Promise.resolve();
        
        return new Promise(resolve => {
            element.style.opacity = '0';
            element.style.display = '';
            element.style.transition = `opacity ${duration}ms ease-out`;
            
            // Trigger reflow
            element.offsetHeight;
            
            element.style.opacity = '1';
            
            setTimeout(resolve, duration);
        });
    }
    
    /**
     * Fade an element out
     */
    function fadeOut(element, duration = 200) {
        if (!element) return Promise.resolve();
        
        return new Promise(resolve => {
            element.style.transition = `opacity ${duration}ms ease-in`;
            element.style.opacity = '0';
            
            setTimeout(() => {
                element.style.display = 'none';
                resolve();
            }, duration);
        });
    }
    
    /**
     * Slide an element down (expand)
     */
    function slideDown(element, duration = 200) {
        if (!element) return Promise.resolve();
        
        return new Promise(resolve => {
            element.style.display = '';
            const height = element.scrollHeight;
            
            element.style.overflow = 'hidden';
            element.style.height = '0';
            element.style.opacity = '0';
            element.style.transition = `height ${duration}ms ease-out, opacity ${duration}ms ease-out`;
            
            // Trigger reflow
            element.offsetHeight;
            
            element.style.height = `${height}px`;
            element.style.opacity = '1';
            
            setTimeout(() => {
                element.style.height = '';
                element.style.overflow = '';
                resolve();
            }, duration);
        });
    }
    
    /**
     * Slide an element up (collapse)
     */
    function slideUp(element, duration = 200) {
        if (!element) return Promise.resolve();
        
        return new Promise(resolve => {
            element.style.overflow = 'hidden';
            element.style.height = `${element.scrollHeight}px`;
            element.style.transition = `height ${duration}ms ease-in, opacity ${duration}ms ease-in`;
            
            // Trigger reflow
            element.offsetHeight;
            
            element.style.height = '0';
            element.style.opacity = '0';
            
            setTimeout(() => {
                element.style.display = 'none';
                element.style.height = '';
                element.style.overflow = '';
                resolve();
            }, duration);
        });
    }
    
    /**
     * Rotate an element
     */
    function rotateIcon(element, degrees, duration = 200) {
        if (!element) return;
        element.style.transition = `transform ${duration}ms ease-out`;
        element.style.transform = `rotate(${degrees}deg)`;
    }
    
    /**
     * Transition between two number values
     */
    function transitionValue(element, oldValue, newValue, duration = 200) {
        if (!element) return Promise.resolve();
        
        return new Promise(resolve => {
            // Fade out
            element.style.transition = `opacity ${duration / 2}ms ease-out`;
            element.style.opacity = '0';
            
            setTimeout(() => {
                element.textContent = newValue;
                element.style.opacity = '1';
                setTimeout(resolve, duration / 2);
            }, duration / 2);
        });
    }
    
    /**
     * Add a pulse effect
     */
    function pulse(element, duration = 500) {
        if (!element) return;
        
        element.style.animation = `pulse ${duration}ms ease-in-out`;
        
        setTimeout(() => {
            element.style.animation = '';
        }, duration);
    }
    
    /**
     * Flash an element (for click feedback)
     */
    function flash(element, duration = 100) {
        if (!element) return;
        
        const originalBorder = element.style.borderColor;
        element.style.borderColor = '#6a6a6a';
        
        setTimeout(() => {
            element.style.borderColor = originalBorder;
        }, duration);
    }
    
    /**
     * Wait for CSS animation to complete
     */
    function onAnimationEnd(element, callback) {
        if (!element || !callback) return;
        
        const handler = () => {
            element.removeEventListener('animationend', handler);
            callback();
        };
        
        element.addEventListener('animationend', handler);
    }
    
    /**
     * Wait for CSS transition to complete
     */
    function onTransitionEnd(element, callback) {
        if (!element || !callback) return;
        
        const handler = () => {
            element.removeEventListener('transitionend', handler);
            callback();
        };
        
        element.addEventListener('transitionend', handler);
    }
    
    /**
     * Simple delay promise
     */
    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    // Public API
    return {
        fadeIn,
        fadeOut,
        slideDown,
        slideUp,
        rotateIcon,
        transitionValue,
        pulse,
        flash,
        onAnimationEnd,
        onTransitionEnd,
        delay
    };
})();
