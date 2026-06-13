/* معروف – منطق النموذج: تحقّق + إرسال + رسالة نجاح */
(function () {
  "use strict";

  const form = document.getElementById("talentForm");
  const submitBtn = document.getElementById("submitBtn");
  const successCard = document.getElementById("successCard");
  const newBtn = document.getElementById("newBtn");
  const toast = document.getElementById("toast");
  const ratingVal = document.getElementById("ratingVal");

  // عرض قيمة تقييم النجوم
  document.querySelectorAll('input[name="level"]').forEach((el) => {
    el.addEventListener("change", () => {
      ratingVal.textContent = el.value + " / 5";
    });
  });

  function showError(input, show) {
    const msg = input.closest(".field")?.querySelector(".err-msg");
    input.classList.toggle("invalid", show);
    if (msg) msg.classList.toggle("show", show);
  }

  function validate() {
    let ok = true;

    // الحقول المطلوبة
    ["full_name", "birth_date", "guardian_phone", "address"].forEach((name) => {
      const input = form.elements[name];
      const empty = !input.value.trim();
      showError(input, empty);
      if (empty) ok = false;
    });

    // رقم الهاتف: 7 أرقام على الأقل
    const phone = form.elements["guardian_phone"];
    if (phone.value.trim()) {
      const digits = phone.value.replace(/\D/g, "");
      if (digits.length < 7) {
        showError(phone, true);
        ok = false;
      }
    }

    // البريد الإلكتروني (اختياري لكن يُتحقّق من صيغته إن وُجد)
    const email = form.elements["email"];
    if (email.value.trim()) {
      const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim());
      showError(email, !valid);
      if (!valid) ok = false;
    } else {
      showError(email, false);
    }

    return ok;
  }

  // إزالة التنبيه عند الكتابة
  form.querySelectorAll("input, textarea").forEach((el) => {
    el.addEventListener("input", () => showError(el, false));
  });

  function showToast(message, isError) {
    toast.textContent = message;
    toast.classList.toggle("error", !!isError);
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 4000);
  }

  function collect() {
    const data = {};
    new FormData(form).forEach((value, key) => { data[key] = value; });
    return data;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!validate()) {
      showToast("الرجاء تعبئة الحقول المطلوبة بشكل صحيح.", true);
      const firstInvalid = form.querySelector(".invalid");
      if (firstInvalid) firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "جارٍ الإرسال...";

    try {
      const res = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collect()),
      });
      const out = await res.json();

      if (res.ok && out.ok) {
        form.style.display = "none";
        successCard.classList.add("show");
        successCard.scrollIntoView({ behavior: "smooth", block: "center" });
      } else {
        showToast(out.message || "حدث خطأ أثناء الإرسال. حاول مرة أخرى.", true);
      }
    } catch (err) {
      showToast("تعذّر الاتصال بالخادم. تحقّق من الإنترنت وحاول مجدداً.", true);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "إرسال الطلب";
    }
  });

  // إرسال طلب آخر
  newBtn.addEventListener("click", () => {
    form.reset();
    ratingVal.textContent = "";
    form.querySelectorAll(".invalid").forEach((el) => el.classList.remove("invalid"));
    form.querySelectorAll(".err-msg.show").forEach((el) => el.classList.remove("show"));
    successCard.classList.remove("show");
    form.style.display = "";
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
})();
