/**
 * settings.js
 */

const themes = ['default', 'dark', 'midnight', 'ocean'];

document.addEventListener('click', (e) => {
    const interactiveElements = ['BUTTON', 'INPUT', 'TEXTAREA', 'A', 'I', 'VIDEO', 'IMG'];
    
    // চেক করা হচ্ছে ক্লিকটি কোনো কার্ড বা ইন্টারেক্টিভ এলিমেন্টে কি না
    if (
        interactiveElements.includes(e.target.tagName) || 
        e.target.closest('.popup-content') || 
        e.target.closest('.cart-bar') ||
        e.target.closest('.add-btn') ||
        e.target.closest('.sort-btn') ||
        e.target.closest('.cat-btn') ||
        
        // ✅ নতুন যুক্ত করা হয়েছে (কার্ডে ক্লিক করলে থিম বদলাবে না)
        e.target.closest('.card') ||          
        e.target.closest('.gallery-card') ||  
        e.target.closest('.lg-outer') ||
        e.target.closest('.lg-container')
    ) {
        return; // থিম পরিবর্তন হবে না
    }

    // থিম পরিবর্তনের লজিক
    let currentTheme = document.documentElement.getAttribute('data-theme') || 'default';
    let currentIndex = themes.indexOf(currentTheme);
    let nextIndex = (currentIndex + 1) % themes.length;
    let nextTheme = themes[nextIndex];

    applyTheme(nextTheme);
});

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('user-theme-pref', theme);
}

window.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('user-theme-pref') || 'default';
    applyTheme(savedTheme);
});
