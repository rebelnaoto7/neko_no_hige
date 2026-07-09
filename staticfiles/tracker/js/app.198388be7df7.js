// ============================================================
// static/tracker/js/app.js（推定パス）
// ねこのひげ - クライアントサイド共通スクリプト
//
// 【機能】
//   1. 右下に出る「猫ウィジェット」の動的生成と吹き出し表示
//   2. 30分ごとに服薬・気圧状況をチェックして猫がしゃべる
//   3. ブラウザ通知（Notification API）の発火
//   4. Chart.js による3種類のグラフ描画
//
// 【ページ側から渡される変数（window グローバル）】
//   window.DUE_MEDS     : boolean - 服薬時刻が来ているか
//   window.LOW_PRESSURE : boolean - 気圧が低いか
//   window.CHART_DATA   : object  - { timeline, scatter, scatter24h }
//
// 【対応するHTML要素】
//   #chartTimeline   : 時系列グラフ用 <canvas>
//   #chartScatter    : 散布図用 <canvas>
//   #chartScatter24h : 24h気圧変化量散布図用 <canvas>
// ============================================================


// ============================================================
// セリフ集（ランダム選択で猫がしゃべる）
// ------------------------------------------------------------
// 3カテゴリの状況別セリフを定義。
// 同じ状況でも毎回違うセリフが出ることで「生き物感」を演出。
// ============================================================
const CAT_LINES_NORMAL = [
    "今日もえらいにゃ",
    "水分とってる？にゃ",
    "無理しないでにゃ〜",
    "ちゃんと記録できてるにゃ"
];
const CAT_LINES_MED = [
    "そろそろお薬の時間にゃ💊",
    "お薬、忘れてないかにゃ？",
    "ひとくち水と一緒にどうぞにゃ",
    "飲んだら『飲んだ🐾』押してにゃ"
];
const CAT_LINES_LOWPRESSURE = [
    "気圧下がってきたにゃ…無理しないでにゃ",
    "今日はゆっくりするにゃ🐾",
    "頭いたくない？休んでにゃ"
];

// 配列からランダムに1要素返す小ヘルパ
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }


// ============================================================
// 猫ウィジェットのDOM生成（冪等）
// ------------------------------------------------------------
// 既に存在していればそれを返し、無ければ動的にDOMを作って
// <body> 末尾に挿入する。
// → ページごとにHTMLを書かなくても、このJSを読み込むだけで
//   全ページに猫が出現する設計。
// ============================================================
function ensureCatWidget() {
    let w = document.getElementById("catWidget");
    if (w) return w;     // 既存があれば再利用

    w = document.createElement("div");
    w.id = "catWidget";
    w.className = "cat-widget";
    // 吹き出し（テキスト表示用）＋猫画像
    w.innerHTML =
        '<div class="cat-widget-bubble" id="catWidgetBubble"></div>' +
        '<img class="cat-widget-img" src="/static/tracker/img/neko.png" alt="neko">';
    document.body.appendChild(w);
    return w;
}


// ============================================================
// 吹き出し表示（8秒後に自動で消える）
// ------------------------------------------------------------
// - .show クラスをトグルすることで CSS 側のアニメーションを発火
// - 連続呼び出しで前のタイマーをクリアし、最後の表示から8秒測り直す
// ============================================================
function showCatBubble(text) {
    const w = ensureCatWidget();
    const bubble = w.querySelector("#catWidgetBubble");
    bubble.textContent = text;
    w.classList.add("show");

    // 前のタイマーが残っていたらキャンセル（チラつき防止）
    clearTimeout(window.__catTimer);
    window.__catTimer = setTimeout(function () {
        w.classList.remove("show");
    }, 8000);
}


// ============================================================
// 服薬・気圧チェック → 適切なセリフを猫にしゃべらせる
// ------------------------------------------------------------
// 優先順位：服薬時刻 > 低気圧 > 通常
// 服薬時はブラウザ通知も追加で発火（バックグラウンドでも気付ける）
// ============================================================
function checkMeds() {
    const due = window.DUE_MEDS || false;
    const lowP = window.LOW_PRESSURE || false;

    if (due) {
        showCatBubble(pick(CAT_LINES_MED));
        notify("ねこのひげ", pick(CAT_LINES_MED));   // OS通知も発火
    } else if (lowP) {
        showCatBubble(pick(CAT_LINES_LOWPRESSURE));
    } else {
        showCatBubble(pick(CAT_LINES_NORMAL));
    }
}


// ============================================================
// ブラウザ通知（Notification API）
// ------------------------------------------------------------
// - API未対応ブラウザは無音で何もしない
// - 許可済みなら通知を出す
// - 未決定なら許可ダイアログを出す（拒否済みなら何もしない）
// ============================================================
function notify(title, body) {
    if (!("Notification" in window)) return;

    if (Notification.permission === "granted") {
        new Notification(title, {
            body: body,
            icon: "/static/tracker/img/neko.png"
        });
    } else if (Notification.permission !== "denied") {
        Notification.requestPermission();
    }
}


// ============================================================
// 猫ウィジェットクリックでセリフを更新
// ------------------------------------------------------------
// document 全体に1つだけ登録（イベント委譲）。
// closest("#catWidget") で猫ウィジェット内のどこをクリックしても反応。
// ============================================================
document.addEventListener("click", function (e) {
    if (e.target.closest("#catWidget")) {
        checkMeds();
    }
});


// ============================================================
// グラフ描画（Chart.js 必須）
// ------------------------------------------------------------
// 該当する <canvas> が存在し、かつデータがあるグラフだけ描画。
// ページごとに必要なグラフだけHTML側に置けばよい設計。
// ============================================================
function renderCharts() {
    // Chart.js 未読み込み時は何もしない（チャートのないページ対応）
    if (typeof Chart === "undefined") return;

    const data = window.CHART_DATA || {};

    // -----------------------------
    // ① 時系列グラフ（折れ線）
    // -----------------------------
    // 痛み(0-10)を左軸、気圧(hPa)を右軸の2軸構成。
    // interaction.mode:"index" でホバー時に同X軸の両データを同時表示。
    const tl = document.getElementById("chartTimeline");
    if (tl && data.timeline) {
        new Chart(tl, {
            type: "line",
            data: data.timeline,
            options: {
                responsive: true,
                interaction: { mode: "index", intersect: false },
                scales: {
                    y: {
                        position: "left",
                        title: { display: true, text: "痛み(0-10)" },
                        min: 0, max: 10
                    },
                    y1: {
                        position: "right",
                        title: { display: true, text: "気圧(hPa)" },
                        grid: { drawOnChartArea: false }    // 二重グリッド回避
                    }
                }
            }
        });
    }

    // -----------------------------
    // ② 散布図（気圧 × 痛み）
    // -----------------------------
    // 気圧と痛みの相関を点で可視化。
    const sc = document.getElementById("chartScatter");
    if (sc && data.scatter) {
        new Chart(sc, {
            type: "scatter",
            data: data.scatter,
            options: {
                scales: {
                    x: { title: { display: true, text: "気圧(hPa)" } },
                    y: { title: { display: true, text: "痛み(0-10)" }, min: 0, max: 10 }
                }
            }
        });
    }

    // -----------------------------
    // ③ 散布図（24h気圧変化量 × 痛み）
    // -----------------------------
    // 「絶対値ではなく前日比」で見た時の相関。
    // マイナスほど気圧低下＝痛み出やすい傾向の検証用。
    const sc24 = document.getElementById("chartScatter24h");
    if (sc24 && data.scatter24h) {
        new Chart(sc24, {
            type: "scatter",
            data: data.scatter24h,
            options: {
                scales: {
                    x: { title: { display: true, text: "24h変化量(hPa)" } },
                    y: { title: { display: true, text: "痛み(0-10)" }, min: 0, max: 10 }
                }
            }
        });
    }
}


// ============================================================
// ページ読み込み完了時の初期化
// ------------------------------------------------------------
//  1. 通知の許可状況が未決定なら、ダイアログを出す
//  2. 猫ウィジェットをDOMに準備
//  3. 1.2秒後に最初のセリフを表示（ページ表示完了の余韻を作る）
//  4. 30分ごとに状況チェック → セリフ更新
//  5. グラフ描画
// ============================================================
window.addEventListener("DOMContentLoaded", function () {
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }
    ensureCatWidget();
    setTimeout(checkMeds, 1200);                    // 初回セリフ
    setInterval(checkMeds, 1000 * 60 * 30);         // 30分間隔
    renderCharts();
});
``