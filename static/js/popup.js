/**
 * popup.js - Handles Popup, Swiper Gallery, and Video Playback
 */

let swiperThumbs = null;
let swiperMain = null;
let selectedVariant = null;

window.openPopup = function(product) {
    const mainTrack = document.getElementById('galleryTrackMain');
    const thumbTrack = document.getElementById('galleryTrackThumbs');
    const detailsArea = document.querySelector('.popup-details');

    // আগের কন্টেন্ট ক্লিয়ার করা
    mainTrack.innerHTML = "";
    thumbTrack.innerHTML = "";
    selectedVariant = null; 

    const mediaList = product.media || [];
    
    // মিডিয়া (ইমেজ/ভিডিও) লুপ
    mediaList.forEach(m => {
        const url = `https://miss-zeba-bot-production.up.railway.app/api/image/${m.file_id}`;
        
        // --- মেইন স্লাইড (বড় ভিউ) ---
        const mainSlide = document.createElement('div');
        mainSlide.className = 'swiper-slide';
        
        if (m.type === 'video') {
            // ভিডিও হলে কন্ট্রোলস সহ দেখাবে
            mainSlide.innerHTML = `
                <div class="swiper-zoom-container">
                    <video src="${url}" 
                           playsinline 
                           controls 
                           controlsList="nodownload" 
                           style="width: 100%; height: 100%; object-fit: contain;">
                    </video>
                </div>`;
        } else {
            // ইমেজ হলে জুম কন্টেইনারে থাকবে
            mainSlide.innerHTML = `
                <div class="swiper-zoom-container">
                    <img src="${url}" style="width: 100%; height: 100%; object-fit: contain;">
                </div>`;
        }
        mainTrack.appendChild(mainSlide);

        // --- থাম্বনেইল স্লাইড (নিচের ছোট ভিউ) ---
        const thumbSlide = document.createElement('div');
        thumbSlide.className = 'swiper-slide';
        
        if (m.type === 'video') {
            // থাম্বনেইলে ভিডিও মিউট করা থাকবে
            thumbSlide.innerHTML = `<video src="${url}" muted playsinline style="object-fit: cover; width: 100%; height: 100%; border-radius: 6px;"></video>`;
        } else {
            thumbSlide.innerHTML = `<img src="${url}" style="object-fit: cover; width: 100%; height: 100%; border-radius: 6px;">`;
        }
        thumbTrack.appendChild(thumbSlide);
    });

    // ভেরিয়েন্ট লজিক
    let variantHTML = "";
    if (product.variants && product.variants.length > 0) {
        variantHTML = `
        <div class="variant-section">
            <p class="variant-label">ভেরিয়েন্ট নির্বাচন করুন:</p>
            <div class="variant-list">
                ${product.variants.map(v => `
                    <button class="v-btn" onclick="selectVariant(this, '${v.name}', ${v.price})">
                        ${v.name}
                    </button>
                `).join('')}
            </div>
        </div>`;
    }

    // পপ-আপ ডিটেইলস ইনজেক্ট করা
    detailsArea.innerHTML = `
        <h3 class="detail-name">${product.name}</h3>
        <div id="popupPrice" class="detail-price">${product.price} TK</div>
        <div class="detail-divider"></div>
        ${variantHTML}
        <p class="detail-desc">${product.description || "কোনো বর্ণনা দেওয়া নেই।"}</p>
        <button class="popup-add-btn" onclick="confirmAddToCart('${product.id}', '${product.name}', ${product.price})">
            <i class="fas fa-cart-plus"></i> কার্টে যোগ করুন
        </button>
    `;

    // পপ-আপ ক্লাস অ্যাড করে ওপেন করা
    document.getElementById('customPopup').classList.add('active');

    // আগের Swiper ডিলেট করা (মেমোরি লিক রোধ করতে)
    if (swiperThumbs) swiperThumbs.destroy();
    if (swiperMain) swiperMain.destroy();

    // Swiper ইনিশিয়ালাইজেশন
    swiperThumbs = new Swiper(".mySwiper", {
        spaceBetween: 10,
        slidesPerView: 4,
        freeMode: true,
        watchSlidesProgress: true,
    });

    swiperMain = new Swiper(".mySwiper2", {
        loop: mediaList.length > 1,
        spaceBetween: 10,
        zoom: { maxRatio: 3 }, // জুম এনিবল
        navigation: {
            nextEl: ".swiper-button-next",
            prevEl: ".swiper-button-prev",
        },
        thumbs: { swiper: swiperThumbs },
        on: {
            // স্লাইড চেঞ্জ হলে ভিডিও পজ/প্লে হ্যান্ডেল করা
            slideChangeTransitionEnd: function() {
                // সব ভিডিও পজ করা
                document.querySelectorAll('.mySwiper2 video').forEach(v => v.pause());
                
                // বর্তমান স্লাইডে ভিডিও থাকলে প্লে করা
                const activeSlide = this.slides[this.activeIndex];
                const activeVideo = activeSlide.querySelector('video');
                if (activeVideo) {
                    activeVideo.currentTime = 0;
                    activeVideo.play().catch(() => {});
                }
            }
        }
    });
};

// ভেরিয়েন্ট সিলেক্ট
window.selectVariant = function(btn, name, price) {
    document.querySelectorAll('.v-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedVariant = { name, price };
    document.getElementById('popupPrice').innerText = price + " TK";
};

// কার্টে অ্যাড
window.confirmAddToCart = function(id, name, basePrice) {
    const finalPrice = selectedVariant ? selectedVariant.price : basePrice;
    const fullName = selectedVariant ? `${name} (${selectedVariant.name})` : name;
    const finalId = selectedVariant ? `${id}-${selectedVariant.name}` : id;
    
    if (window.addToCart) {
        window.addToCart(finalId, fullName, finalPrice);
    }
    window.closePopup();
};

// পপ-আপ ক্লোজ
window.closePopup = function() {
    document.getElementById('customPopup').classList.remove('active');
    // পপ-আপ বন্ধ করলে ভিডিও পজ হয়ে যাবে
    document.querySelectorAll('video').forEach(v => v.pause());
};
