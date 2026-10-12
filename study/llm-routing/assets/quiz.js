// Multiple-choice quiz component.
//
// Markup:
//   <div class="quiz" data-score-target="#score">
//     <div class="quiz-item" data-correct="b">
//       <p class="prompt">...</p>
//       <div class="choices">
//         <button data-choice="a">...</button>
//         <button data-choice="b">...</button>
//       </div>
//       <div class="explain">...</div>
//     </div>
//   </div>
//   <p class="quiz-score" id="score"></p>
//
// Each item locks after the first click, marks the right and wrong buttons,
// and reveals its explanation. The score line updates as items are answered.

(function () {
  function initQuiz(quiz) {
    const items = Array.from(quiz.querySelectorAll(".quiz-item"));
    const scoreEl = quiz.dataset.scoreTarget
      ? document.querySelector(quiz.dataset.scoreTarget)
      : null;
    let answered = 0;
    let right = 0;

    function renderScore() {
      if (!scoreEl) return;
      scoreEl.textContent =
        answered === items.length
          ? `You got ${right} of ${items.length}. Re-read the explanations for any you missed, then try again in a few days without looking.`
          : `${answered} of ${items.length} answered.`;
    }

    items.forEach((item) => {
      const correct = item.dataset.correct;
      const buttons = Array.from(item.querySelectorAll(".choices button"));
      const explain = item.querySelector(".explain");

      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          if (item.classList.contains("answered")) return;
          const isRight = button.dataset.choice === correct;
          item.classList.add("answered");
          buttons.forEach((b) => {
            b.disabled = true;
            if (b.dataset.choice === correct) b.classList.add("correct");
          });
          if (!isRight) button.classList.add("wrong");
          if (explain) {
            const verdict = document.createElement("span");
            verdict.className = isRight ? "verdict-good" : "verdict-bad";
            verdict.textContent = isRight ? "Right. " : "Not quite. ";
            explain.prepend(verdict);
          }
          answered += 1;
          if (isRight) right += 1;
          renderScore();
        });
      });
    });

    renderScore();
  }

  document.querySelectorAll(".quiz").forEach(initQuiz);
})();
