const roleContent = {
  "product-manager": {
    label: "产品经理",
    interviewer: "林然",
    image: "/app/assets/visuals/interview-coach-hero.jpg",
    imageAlt: "一位产品面试官坐在现代办公室中",
    imageClass: "role-product",
    questions: [
      ["pm-impact", "讲一个你推动产品指标提升的项目。"],
      ["pm-conflict", "讲一次你和研发或业务方发生分歧时如何推进。"],
    ],
    first: "我做过一个增长项目，后来效果明显变好。",
    second:
      "当时新用户首单转化率是18%。我负责拆解漏斗，推动研发上线价格说明和默认优惠选择，并用A/B实验验证。四周后转化率提升到26%，投诉下降15%。",
  },
  "algorithm-engineer": {
    label: "算法工程师",
    interviewer: "周谨",
    image: "/app/assets/visuals/interview-coach-hero.jpg",
    imageAlt: "一位算法面试官坐在现代办公室中",
    imageClass: "role-algorithm",
    questions: [
      ["algo-tradeoff", "讲一次你在模型效果和线上性能之间做权衡的经历。"],
      ["algo-debug", "讲一次你定位模型效果下降的经历。"],
    ],
    first: "我们换了一个模型，准确率好了一些，最后也顺利上线了。",
    second:
      "离线准确率提升3.2个百分点，但P95延迟增加48毫秒。我负责做分桶评测和特征裁剪，把延迟压回20毫秒内，最终灰度覆盖30%流量且核心指标不回退。",
  },
  sales: {
    label: "销售",
    interviewer: "苏琳",
    image: "/app/assets/visuals/interview-coach-hero.jpg",
    imageAlt: "一位销售面试官坐在现代办公室中",
    imageClass: "role-sales",
    questions: [
      ["sales-objection", "讲一次你处理关键客户异议并推动成交的经历。"],
      ["sales-pipeline", "讲一次你如何管理销售漏斗并提升转化。"],
    ],
    first: "客户觉得预算太高，我和他沟通了几次，后来客户同意合作。",
    second:
      "客户担心首年预算超支。我先确认决策人最在意回本周期，再把方案拆成两阶段试点，并用同规模客户数据测算收益。两周后完成45万元签约，回款周期缩短到30天。",
  },
  operations: {
    label: "运营",
    interviewer: "陈澄",
    image: "/app/assets/visuals/interview-coach-hero.jpg",
    imageAlt: "一位运营面试官坐在现代办公室中",
    imageClass: "role-operations",
    questions: [
      ["ops-growth", "讲一次你用运营动作带来增长的经历。"],
      ["ops-crisis", "讲一次你处理线上运营事故或舆情的经历。"],
    ],
    first: "我们做了一次活动，用户参与很多，整体效果还可以。",
    second:
      "活动前新用户次日留存只有21%。我负责调整新手任务、社群触达和渠道节奏，并按渠道每天复盘。活动两周后次日留存提升到28%，获客成本下降12%。",
  },
};

const scoreLabels = {
  structure: "表达结构",
  specificity: "具体程度",
  metrics: "结果数据",
  role_fit: "岗位匹配",
  clarity: "表达清晰",
  risk_control: "真实可信",
};

const issueCopy = {
  STAR_INCOMPLETE: ["结构不完整", "按背景、任务、行动、结果重新组织。"],
  NO_METRIC: ["缺少结果数字", "补充转化、周期、人数或收入等结果。"],
  LOW_ROLE_FIT: ["岗位动作不具体", "说清楚你用了什么方法，解决了什么问题。"],
  VAGUE_LANGUAGE: ["表达有些模糊", "把“一些”“明显”等词换成事实。"],
  NO_OWNERSHIP: ["个人贡献不清楚", "说明你本人负责的动作和判断。"],
};

const positiveCopy = [
  ["结构完整", "背景、行动和结果都能快速听懂。"],
  ["数字具体", "结果有量化信息，可信度更高。"],
  ["贡献清楚", "能分辨你本人完成了什么。"],
];

const state = {
  role: "product-manager",
  questionIndex: 0,
  attempt: 1,
  result: null,
  speaking: false,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function initialize() {
  bindEvents();
  renderRole();
  updateCount();
  checkService();
  setupSpotlight();
  refreshIcons();

  if (new URLSearchParams(window.location.search).get("demo") === "1") {
    loadExample();
  }
}

function bindEvents() {
  $$(".role-button").forEach((button) => {
    button.addEventListener("click", () => selectRole(button.dataset.role));
  });
  $("#next-question").addEventListener("click", nextQuestion);
  $("#load-example").addEventListener("click", loadExample);
  $("#analyze-answer").addEventListener("click", analyzeAnswer);
  $("#answer").addEventListener("input", updateCount);
  $("#upload-audio").addEventListener("click", () => $("#audio-input").click());
  $("#audio-input").addEventListener("change", transcribeAudio);
  $("#read-question").addEventListener("click", readQuestion);
  $("#close-detail").addEventListener("click", () => $("#detail-dialog").close());
}

function selectRole(role) {
  if (!roleContent[role] || role === state.role) return;
  state.role = role;
  state.questionIndex = 0;
  state.attempt = 1;
  state.result = null;
  $$(".role-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.role === role);
  });
  renderRole();
  resetAnswer();
  animateQuestion();
}

function renderRole() {
  const role = activeRole();
  const question = activeQuestion()[1];
  $("#question").textContent = question;
  $("#stage-question").textContent = question;
  $("#stage-role").textContent = `${role.label}面试`;
  $("#interviewer-name").textContent = role.interviewer;
  const image = $(".interviewer-image");
  image.className = `interviewer-image ${role.imageClass}`;
  image.style.opacity = "0.68";
  window.setTimeout(() => {
    image.src = role.image;
    image.alt = role.imageAlt;
    image.style.opacity = "1";
  }, 120);
  document.title = `${role.label}练习 · 面试陪练`;
}

function nextQuestion() {
  state.questionIndex =
    (state.questionIndex + 1) % activeRole().questions.length;
  state.attempt = 1;
  state.result = null;
  renderRole();
  resetAnswer();
  animateQuestion();
}

function resetAnswer() {
  $("#answer").value = "";
  $("#answer").placeholder =
    "像面对真实面试官一样回答。重点说清楚：背景、你做了什么、结果如何。";
  updateCount();
  renderEmpty();
  setProgress("answer");
  $("#answer").focus();
}

function loadExample() {
  const answer =
    state.attempt === 1 ? activeRole().first : activeRole().second;
  $("#answer").value = answer;
  updateCount();
  $("#answer").focus();
  $("#answer").animate(
    [
      { backgroundColor: "#f8ddd5" },
      { backgroundColor: "rgba(246, 242, 235, 0.7)" },
    ],
    { duration: 620, easing: "ease-out" },
  );
}

async function analyzeAnswer() {
  const answer = $("#answer").value.trim();
  if (!answer) {
    showToast("先说一段真实经历");
    $("#answer").focus();
    return;
  }

  setButtonBusy($("#analyze-answer"), true, "分析中");
  try {
    const payload =
      state.attempt === 1
        ? {
            role: state.role,
            question_id: activeQuestion()[0],
            answer,
          }
        : {
            role: state.role,
            question_id: activeQuestion()[0],
            answer: state.result.first_answer.answer,
            second_answer: answer,
          };
    const response = await fetch("/v1/interview/coach", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error?.message || `HTTP ${response.status}`);
    }
    state.result = data.result;
    renderResult();
    setProgress(state.attempt === 1 ? "feedback" : "retry");
  } catch (error) {
    showToast(`分析失败：${error.message}`);
  } finally {
    setButtonBusy($("#analyze-answer"), false);
  }
}

function renderResult() {
  const resultPanel = $("#result-panel");
  const isSecond = state.attempt === 2 && Boolean(state.result.second_answer);
  const attempt = isSecond
    ? state.result.second_answer
    : state.result.first_answer;
  const feedback = isSecond
    ? positiveCopy.map((item) => [...item])
    : attempt.issues
        .slice(0, 3)
        .map((item) => issueCopy[item.code] || [item.message, item.detail]);

  while (feedback.length < 3) {
    feedback.push([...positiveCopy[feedback.length]]);
  }

  const delta = isSecond ? state.result.comparison.total_delta : null;
  resultPanel.classList.remove("is-empty");
  resultPanel.innerHTML = `
    <div class="result-content">
      <div class="result-title">
        <div class="score-block">
          <strong>${attempt.total_score.toFixed(1)}</strong>
          <span>/ 7</span>
        </div>
        <div class="result-summary">
          <strong>${isSecond ? "这次更有说服力" : "先改这三点"}</strong>
          ${
            isSecond
              ? `<span class="score-change"><i data-lucide="trending-up"></i> 提升 ${delta.toFixed(1)} 分</span>`
              : "<span>改完后，再答一次</span>"
          }
        </div>
      </div>
      <div class="feedback-list">
        ${feedback
          .map(
            ([title, detail], index) => `
              <article class="feedback-item ${isSecond ? "is-positive" : ""}">
                <span class="feedback-number">${isSecond ? "✓" : index + 1}</span>
                <div>
                  <strong>${escapeHtml(title)}</strong>
                  <p>${escapeHtml(detail)}</p>
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
      <div class="result-actions">
        <p class="followup">
          <strong>${isSecond ? "继续追问：" : "面试官可能会问："}</strong>
          ${escapeHtml(attempt.followups[0])}
        </p>
        <div>
          <button class="text-button" id="show-detail" type="button">
            完整建议
          </button>
          ${
            isSecond
              ? `
                <button class="text-button report-button" id="download-report" type="button">
                  <i data-lucide="download"></i>
                  下载报告
                </button>
              `
              : ""
          }
          <button class="secondary-button" id="${isSecond ? "new-question" : "retry-answer"}" type="button">
            ${isSecond ? "再练一题" : "再答一次"}
            <i data-lucide="${isSecond ? "refresh-cw" : "arrow-right"}"></i>
          </button>
        </div>
      </div>
    </div>
  `;

  $("#show-detail").addEventListener("click", openDetail);
  if (isSecond) {
    $("#download-report").addEventListener("click", downloadReport);
    $("#new-question").addEventListener("click", nextQuestion);
  } else {
    $("#retry-answer").addEventListener("click", startSecondAttempt);
  }
  refreshIcons();
}

async function downloadReport() {
  const button = $("#download-report");
  if (!state.result?.second_answer) return;
  setButtonBusy(button, true, "生成中");
  try {
    const response = await fetch("/v1/interview/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role: state.result.role,
        question_id: state.result.question_id,
        answer: state.result.first_answer.answer,
        second_answer: state.result.second_answer.answer,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error?.message || `HTTP ${response.status}`);
    }
    const blob = new Blob([data.markdown], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = data.filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    showToast("练习报告已下载");
  } catch (error) {
    showToast(`报告生成失败：${error.message}`);
  } finally {
    setButtonBusy(button, false);
  }
}

function startSecondAttempt() {
  state.attempt = 2;
  $("#answer").value = "";
  $("#answer").placeholder =
    "现在再答一次：把背景、你的动作和结果数字说清楚。";
  updateCount();
  setProgress("retry");
  $("#answer").focus();
  showToast("保留真实经历，只补足表达");
}

function openDetail() {
  const attempt =
    state.attempt === 2 && state.result.second_answer
      ? state.result.second_answer
      : state.result.first_answer;
  $("#score-grid").innerHTML = Object.entries(attempt.scores)
    .map(
      ([key, score]) => `
        <div class="score-row">
          <span>${scoreLabels[key]}</span>
          <strong>${score} / 7</strong>
          <span class="score-bar"><i style="width:${(score / 7) * 100}%"></i></span>
        </div>
      `,
    )
    .join("");
  $("#rewrite-text").textContent = compactRewrite(attempt.rewrite);
  $("#detail-dialog").showModal();
}

async function transcribeAudio(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".wav")) {
    showToast("请导入 WAV 录音");
    event.target.value = "";
    return;
  }

  setButtonBusy($("#upload-audio"), true, "转写中");
  try {
    const audioBase64 = arrayBufferToBase64(await file.arrayBuffer());
    const response = await fetch("/v1/interview/transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio_base64: audioBase64, language: "zh" }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error?.message || `HTTP ${response.status}`);
    }
    $("#answer").value = data.text;
    updateCount();
    showToast("语音已在本机转成文字");
  } catch (error) {
    showToast(`转写失败：${error.message}`);
  } finally {
    event.target.value = "";
    setButtonBusy($("#upload-audio"), false);
  }
}

function readQuestion() {
  if (!("speechSynthesis" in window)) {
    showToast("当前浏览器不支持朗读");
    return;
  }
  if (state.speaking) {
    window.speechSynthesis.cancel();
    resetReadButton();
    return;
  }

  const utterance = new SpeechSynthesisUtterance(activeQuestion()[1]);
  utterance.lang = "zh-CN";
  utterance.rate = 0.93;
  utterance.onend = resetReadButton;
  state.speaking = true;
  $("#read-question").innerHTML =
    '<i data-lucide="square"></i><span>停止</span>';
  refreshIcons();
  window.speechSynthesis.speak(utterance);
}

function resetReadButton() {
  state.speaking = false;
  $("#read-question").innerHTML =
    '<i data-lucide="volume-2"></i><span>听问题</span>';
  refreshIcons();
}

function setProgress(step) {
  const order = ["answer", "feedback", "retry"];
  const current = order.indexOf(step);
  $$(".progress-step").forEach((item, index) => {
    item.classList.toggle("is-active", index === current);
    item.classList.toggle("is-done", index < current);
  });
  $$(".progress-track").forEach((item, index) => {
    item.classList.toggle("is-done", index < current);
  });
}

function renderEmpty() {
  $("#result-panel").className = "result-panel is-empty";
  $("#result-panel").innerHTML = `
    <div class="empty-result">
      <span class="empty-icon"><i data-lucide="message-circle-more"></i></span>
      <div>
        <strong>说完就能改</strong>
        <p>我们只给最值得先改的三点。</p>
      </div>
    </div>
  `;
  refreshIcons();
}

async function checkService() {
  try {
    const response = await fetch("/v1/status");
    if (!response.ok) throw new Error("status");
    const data = await response.json();
    $("#service-state").classList.add("is-ready");
    $("#service-label").textContent =
      data.state === "ready" ? "本地陪练已就绪" : "正在处理";
  } catch {
    $("#service-label").textContent = "离线演示";
  }
}

function setupSpotlight() {
  const panel = $(".spotlight-panel");
  panel.addEventListener("pointermove", (event) => {
    const rect = panel.getBoundingClientRect();
    panel.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
    panel.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
  });
}

function animateQuestion() {
  [$("#question"), $("#stage-question")].forEach((element) => {
    element.animate(
      [
        { opacity: 0, transform: "translateY(8px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 380, easing: "cubic-bezier(0.16, 1, 0.3, 1)" },
    );
  });
}

function updateCount() {
  $("#answer-count").textContent = `${$("#answer").value.length} / 500`;
}

function activeRole() {
  return roleContent[state.role];
}

function activeQuestion() {
  return activeRole().questions[state.questionIndex];
}

function setButtonBusy(button, busy, label) {
  if (busy) {
    button.dataset.original = button.innerHTML;
    button.disabled = true;
    button.classList.add("is-loading");
    button.innerHTML = `<i data-lucide="loader-circle"></i><span>${label}</span>`;
  } else {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.innerHTML = button.dataset.original;
  }
  refreshIcons();
}

function compactRewrite(text) {
  return text
    .replace(/原始回答：.*?已提供事实：/u, "")
    .replace("以上只使用你已经提供的信息；方括号处需要你本人补充。", "")
    .trim();
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(
    () => toast.classList.remove("is-visible"),
    2200,
  );
}

initialize();
