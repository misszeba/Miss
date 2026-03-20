document.addEventListener("DOMContentLoaded", () => {
  // === ১. টেলিগ্রাম সেটআপ ===
  const tg = window.Telegram.WebApp;
  if (tg) {
    tg.expand();
    // হ্যাপ্টিক ফিডব্যাক সেফটি চেক
    if (!tg.isVersionAtLeast || !tg.isVersionAtLeast("6.2")) {
      if (!tg.HapticFeedback) tg.HapticFeedback = { impactOccurred: () => {} };
    }
  }

  // === ২. ভেরিয়েবল ডিক্লারেশন ===
  let allProducts = [];
  let cart = {};
  let currentCategory = "all";
  let currentSort = "default";
  let currentLayout = "grid"; // ডিফল্ট

  const shopId = new URLSearchParams(window.location.search).get("id");

  const productList = document.getElementById("productList");
  const catList = document.getElementById("catList");
  const searchInput = document.getElementById("searchInput");
  const layoutToggle = document.getElementById("layoutToggle");
  const cartBar = document.getElementById("cartBar");

  // === ৩. ডাটা ফেচিং ===
  fetch(`/api/products/${shopId}`)
    .then(res => res.json())
    .then(data => {
      if (data.products) {
        allProducts = Object.keys(data.products).map(key => ({
          id: key,
          ...data.products[key],
        }));
      }
      renderCategories(data.categories || {});
      renderProducts(allProducts);
    })
    .catch(err => console.error("Data loading error:", err));

  function renderCategories(categories) {
    if (!catList) return;
    catList.innerHTML = `<button class="cat-btn active" data-id="all">সবগুলো</button>`;
    for (let id in categories) {
      let btn = document.createElement("button");
      btn.className = "cat-btn";
      btn.dataset.id = id;
      btn.innerText = categories[id];
      catList.appendChild(btn);
    }
  }

  // === ৪. প্রোডাক্ট রেন্ডার ফাংশন (Instagram Grid + Variant Logic) ===
  function renderProducts(products) {
    if (!productList) return;
    productList.innerHTML =
      products.length === 0 ? '<p class="loading">কিছু পাওয়া যায়নি</p>' : "";

    products.forEach(p => {
      // --- Gallery View (Instagram Grid Style) ---
      if (currentLayout === "gallery") {
        const mediaList = p.media || [];
        const card = document.createElement("div");
        card.className = "gallery-card modern-card";

        // Spotlight কনফিগারেশন
        const spotlightConfig = `
                    class="spotlight"
                    data-spotlight="group-${p.id}"
                    data-title="${p.name}"
                    data-description="দাম: ${p.price} TK"
                    data-effect="slide"
                    data-theme="white"
                    data-control="autofit,zoom,close"
                `;

        // মিডিয়া গ্রিড তৈরি
        let gridItemsHTML = mediaList
          .map(m => {
            const url = `https://miss-zeba-bot-production.up.railway.app/api/image/${m.file_id}`;

            if (m.type === "video") {
              return `
                        <a href="${url}#.mp4" ${spotlightConfig} data-media="video" class="grid-item video-item">
                            <video poster="ammu.jpeg" src="${url}" muted loop playsinline class="grid-img"></video>
                            <div class="grid-play-icon"><i class="fas fa-play"></i></div>
                        </a>`;
            } else {
              return `
                        <a href="${url}" ${spotlightConfig} class="grid-item">
                            <img src="${url}" class="grid-img" loading="lazy" alt="${p.name}" />
                        </a>`;
            }
          })
          .join("");

        // 🔥 ভেরিয়েন্ট বাটন লজিক (Variant Buttons)
        let variantHTML = "";
        if (p.variants && p.variants.length > 0) {
          variantHTML = `
                    <div class="variant-section-modern" style="margin-top: 15px;">
                        <div style="width:100%; font-size:12px; color:#666; margin-bottom:5px;">প্যাকেজ সিলেক্ট করুন:</div>
                        ${p.variants
                          .map(
                            (v, i) => `
                        <button class="v-btn-modern ${i === 0 ? "active" : ""}" 
                            data-price="${v.price}" 
                            data-name="${v.name}"
                            onclick="window.updateGalleryCardPrice(this, '${
                              p.id
                            }')">
                            ${v.name}
                        </button>`
                          )
                          .join("")}
                    </div>`;
        }

        card.innerHTML = `
                    <div class="card-header">
                        <h3 class="modern-title">${p.name}</h3>
                        <span id="price-${p.id}" class="modern-price-tag">${p.price} TK</span>
                    </div>

                    <div class="media-grid-container">
                        ${gridItemsHTML}
                    </div>

                    ${variantHTML}

                    <button class="add-btn-modern" style="margin-top: 15px;" onclick="window.handleGalleryAdd('${p.id}', '${p.name}')">
                        <span>অর্ডার করুন</span>
                        <i class="fas fa-shopping-bag"></i>
                    </button>
                `;
        productList.appendChild(card);
      } else {
        // --- GRID / LIST View (Standard) ---
        let thumbHTML = "";
        if (p.media && p.media.length > 0) {
          const firstMedia = p.media[0];
          const url = `https://miss-zeba-bot-production.up.railway.app/api/image/${firstMedia.file_id}`;

          if (firstMedia.type === "video") {
            thumbHTML = `
                            <div class="video-wrapper">
                                <video poster="ammu.jpeg" src="${url}" class="p-img autoplay-video" muted loop autoplay playsinline preload="auto" style="object-fit:cover;"></video>
                            </div>`;
          } else {
            thumbHTML = `<img src="${url}" class="p-img" loading="lazy">`;
          }
        } else {
          thumbHTML = `<img src="https://via.placeholder.com/300" class="p-img">`;
        }

        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
                    <div class="card-img-box">${thumbHTML}</div>
                    <div class="card-info">
                        <div class="prod-name">${p.name}</div>
                        <div class="prod-price">${p.price} TK</div>
                        <button class="add-btn" data-id="${p.id}">
                            <i class="fas fa-plus"></i> ADD
                        </button>
                    </div>`;
        productList.appendChild(card);
      }
    });

    // ভিডিও অটো-প্লে হ্যান্ডলার
    setTimeout(() => {
      const videos = document.querySelectorAll(
        ".video-item video, .autoplay-video"
      );
      videos.forEach(v => {
        if (v.tagName === "VIDEO") {
          let playPromise = v.play();
          if (playPromise !== undefined) {
            playPromise.catch(() => {
              v.muted = true; // অটো-প্লে ফেইল করলে মিউট করে আবার ট্রাই করবে
              v.play();
            });
          }
        }
      });
    }, 500);
  }

  // === ৫. ইভেন্ট লিসেনার (General) ===
  if (productList) {
    productList.addEventListener("click", e => {
      // গ্রিড ভিউতে কার্ডে ক্লিক -> পপআপ ওপেন (Spotlight বাদে)
      if (currentLayout !== "gallery") {
        // Add Button লজিক
        const btn = e.target.closest(".add-btn");
        if (btn) {
          const product = allProducts.find(p => p.id === btn.dataset.id);
          if (product) {
            if (product.variants?.length > 0 && window.openPopup)
              window.openPopup(product);
            else window.addToCart(product.id, product.name, product.price);
          }
          return;
        }

        // Card Click -> Popup
        const card = e.target.closest(".card");
        if (card) {
          const pId = card.querySelector(".add-btn")?.dataset.id;
          const product = allProducts.find(p => p.id === pId);
          if (product && window.openPopup) {
            window.openPopup(product);
          }
        }
      }
    });
  }

  // === ৬. হেল্পার ফাংশনস (Window Scope - ভেরিয়েন্ট লজিক) ===

  // 🔥 ১. ভেরিয়েন্ট বাটনে ক্লিক করলে দাম আপডেট হবে
  window.updateGalleryCardPrice = function (btn, pId) {
    // ১. একটিভ বাটন পরিবর্তন
    const parent = btn.parentElement;
    parent
      .querySelectorAll(".v-btn-modern")
      .forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    // ২. নতুন দাম নেওয়া
    const newPrice = btn.getAttribute("data-price");

    // ৩. UI তে দাম আপডেট করা (হেডার অংশে)
    const priceElement = document.getElementById(`price-${pId}`);
    if (priceElement) {
      priceElement.innerText = newPrice + " TK";
      // ছোট্ট এনিমেশন ইফেক্ট
      priceElement.style.transform = "scale(1.2)";
      setTimeout(() => (priceElement.style.transform = "scale(1)"), 200);
    }
  };

  // 🔥 ২. গ্যালারি কার্ড থেকে অর্ডার হ্যান্ডলার
  window.handleGalleryAdd = function (pId, pName) {
    // ১. বর্তমান ডিসপ্লে করা দাম নেওয়া
    const priceText = document.getElementById(`price-${pId}`).innerText;

    // ২. সিলেক্ট করা ভেরিয়েন্টের নাম বের করা
    const priceElement = document.getElementById(`price-${pId}`);
    const card = priceElement.closest(".gallery-card");
    const activeVariant = card.querySelector(".v-btn-modern.active");

    // ৩. যদি ভেরিয়েন্ট থাকে তবে নামের সাথে যুক্ত করা
    const finalName = activeVariant
      ? `${pName} (${activeVariant.getAttribute("data-name")})`
      : pName;

    // ৪. কার্টে পাঠানো
    window.addToCart(pId, finalName, priceText);
  };

  // === ৭. ফিল্টারিং ও সর্টিং ===
  function applyFilters() {
    let term = (searchInput ? searchInput.value : "").toLowerCase();
    let filtered = allProducts.filter(p => {
      let isCat = currentCategory === "all" || p.category === currentCategory;
      let isSearch = p.name.toLowerCase().includes(term);
      return isCat && isSearch;
    });

    if (currentSort === "low") filtered.sort((a, b) => a.price - b.price);
    else if (currentSort === "high") filtered.sort((a, b) => b.price - a.price);
    renderProducts(filtered);
  }

  window.toggleSort = function () {
    const btn = document.getElementById("sortToggleBtn");
    const icon = document.getElementById("sortIcon");
    if (currentSort === "default") {
      currentSort = "low";
      btn.classList.add("active");
      icon.className = "fas fa-sort-amount-down-alt";
    } else if (currentSort === "low") {
      currentSort = "high";
      btn.classList.add("active");
      icon.className = "fas fa-sort-amount-up";
    } else {
      currentSort = "default";
      btn.classList.remove("active");
      icon.className = "fas fa-sort";
    }
    applyFilters();
  };

  if (layoutToggle) {
    layoutToggle.addEventListener("click", () => {
      const icon = document.getElementById("layoutIcon");
      if (currentLayout === "grid") {
        currentLayout = "list";
        productList.className = "product-grid list-view";
        icon.className = "fas fa-list";
      } else if (currentLayout === "list") {
        currentLayout = "gallery";
        productList.className = "product-grid gallery-view";
        icon.className = "fas fa-images"; // এখন এটি ইনস্টাগ্রাম গ্রিড স্টাইল দেখাবে
      } else {
        currentLayout = "grid";
        productList.className = "product-grid";
        icon.className = "fas fa-th-large";
      }
      applyFilters();
    });
  }

  if (searchInput) searchInput.addEventListener("input", applyFilters);
  if (catList) {
    catList.addEventListener("click", e => {
      const btn = e.target.closest(".cat-btn");
      if (btn) {
        document
          .querySelectorAll(".cat-btn")
          .forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentCategory = btn.dataset.id;
        applyFilters();
      }
    });
  }

  // === ৮. কার্ট লজিক ===
  window.addToCart = function (id, name, priceStr) {
    let price = parseFloat(String(priceStr).replace(/[^0-9.]/g, "")) || 0;
    if (!cart[id]) cart[id] = { name, price, qty: 0 };
    cart[id].qty++;
    updateCartUI();
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred("medium");

    // টোস্ট নোটিফিকেশন (অপশনাল)
    showToast("✅ কার্টে যোগ হয়েছে!");
  };

  function updateCartUI() {
    let count = 0,
      total = 0;
    for (let k in cart) {
      count += cart[k].qty;
      total += cart[k].price * cart[k].qty;
    }
    if (document.getElementById("cartCount"))
      document.getElementById("cartCount").innerText = count;
    if (document.getElementById("totalAmount"))
      document.getElementById("totalAmount").innerText = total + " TK";
    if (count > 0 && cartBar) cartBar.classList.add("visible");
  }

  // ছোট টোস্ট মেসেজ দেখানোর ফাংশন
  function showToast(msg) {
    let toast = document.createElement("div");
    toast.className = "toast-msg";
    toast.innerText = msg;
    toast.style.cssText = `
            position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
            background: rgba(0,0,0,0.8); color: white; padding: 10px 20px;
            border-radius: 20px; z-index: 9999; font-size: 14px;
        `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
  }

  if (cartBar) {
    cartBar.addEventListener("click", () => {
      const shopId = new URLSearchParams(window.location.search).get("id");
      if (!tg.initData) {
        alert(`🛒 অর্ডার: ${document.getElementById("totalAmount").innerText}`);
      } else {
        tg.sendData(
          JSON.stringify({ action: "web_order", shop_id: shopId, cart })
        );
      }
    });
  }
});
