const API_URL = "";


// ============================================================
// DOM ELEMENTS
// ============================================================

const internshipsContainer =
    document.getElementById("internshipsContainer");

const loading =
    document.getElementById("loading");

const emptyState =
    document.getElementById("emptyState");

const errorState =
    document.getElementById("errorState");

const errorMessage =
    document.getElementById("errorMessage");

const refreshButton =
    document.getElementById("refreshButton");

const retryButton =
    document.getElementById("retryButton");

const totalJobs =
    document.getElementById("totalJobs");

const activeSubscribers =
    document.getElementById("activeSubscribers");

const notificationsSent =
    document.getElementById("notificationsSent");


// ============================================================
// HELPERS
// ============================================================

function escapeHtml(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


// ============================================================
// RELATIVE TIME
// ============================================================

function getRelativeTime(dateValue) {

    if (!dateValue) {
        return "Recently";
    }

    const date = new Date(dateValue);

    if (Number.isNaN(date.getTime())) {
        return "Recently";
    }

    const now = new Date();

    const difference =
        now.getTime() - date.getTime();

    const seconds =
        Math.floor(difference / 1000);

    if (seconds < 60) {
        return "Discovered just now";
    }

    const minutes =
        Math.floor(seconds / 60);

    if (minutes < 60) {
        return `Discovered ${minutes} minute${minutes === 1 ? "" : "s"} ago`;
    }

    const hours =
        Math.floor(minutes / 60);

    if (hours < 24) {
        return `Discovered ${hours} hour${hours === 1 ? "" : "s"} ago`;
    }

    const days =
        Math.floor(hours / 24);

    if (days < 7) {
        return `Discovered ${days} day${days === 1 ? "" : "s"} ago`;
    }

    return `Discovered ${date.toLocaleDateString()}`;
}


// ============================================================
// SCORE
// ============================================================

function getScore(internship) {

    let score =
        internship.relevance_score;

    if (
        score === null ||
        score === undefined ||
        score === ""
    ) {
        return null;
    }

    score = Number(score);

    if (Number.isNaN(score)) {
        return null;
    }

    return Math.max(
        0,
        Math.min(
            100,
            score
        )
    );
}


// ============================================================
// SCORE CLASS
// ============================================================

function getScoreClass(score) {

    if (score === null) {
        return "score-neutral";
    }

    if (score > 80) {
        return "score-high";
    }

    if (score >= 50) {
        return "score-medium";
    }

    return "score-low";
}


// ============================================================
// SCORE LABEL
// ============================================================

function getScoreLabel(score) {

    if (score === null) {
        return "Score unavailable";
    }

    if (score > 80) {
        return `🔥 ${score}% Match`;
    }

    if (score >= 50) {
        return `⚡ ${score}% Match`;
    }

    return `${score}% Match`;
}


// ============================================================
// SOURCE
// ============================================================

function getSource(internship) {

    const via =
        internship.via;

    const source =
        internship.source;

    if (
        via &&
        String(via).trim()
    ) {
        return String(via).trim();
    }

    if (
        source &&
        String(source).trim()
    ) {
        return String(source).trim();
    }

    return "Automated Search";
}


// ============================================================
// LOCATION
// ============================================================

function getLocation(internship) {

    if (
        internship.location &&
        String(internship.location).trim()
    ) {
        return String(internship.location).trim();
    }

    return "Location not specified";
}


// ============================================================
// DATE FIELD
// ============================================================

function getDateValue(internship) {

    const possibleFields = [
        "created_at",
        "discovered_at",
        "found_at",
        "createdAt",
        "discoveredAt"
    ];

    for (const field of possibleFields) {

        if (internship[field]) {
            return internship[field];
        }

    }

    return null;
}


// ============================================================
// APPLY URL
// ============================================================

function getApplyUrl(internship) {

    if (
        internship.url &&
        String(internship.url).trim()
    ) {
        return String(internship.url).trim();
    }

    return "#";
}


// ============================================================
// SHOW / HIDE
// ============================================================

function showLoading() {

    loading.classList.remove("hidden");

    emptyState.classList.add("hidden");

    errorState.classList.add("hidden");

    internshipsContainer.innerHTML = "";
}


function hideLoading() {

    loading.classList.add("hidden");
}


// ============================================================
// LOAD ANALYTICS
// ============================================================

async function loadAnalytics() {

    try {

        const subscriptionResponse =
            await fetch(
                `${API_URL}/subscriptions`
            );

        if (subscriptionResponse.ok) {

            const subscriptions =
                await subscriptionResponse.json();

            const activeEmails =
                new Set();

            subscriptions.forEach(
                subscription => {

                    if (
                        subscription.is_active &&
                        subscription.user_email
                    ) {
    activeEmails.add(
        String(subscription.user_email).trim().toLowerCase()
    );
}

                }
            );

            activeSubscribers.textContent =
                activeEmails.size;
        }


        // ====================================================
        // NOTIFICATIONS
        // ====================================================

        try {

            const notificationResponse =
                await fetch(
                    `${API_URL}/notifications`
                );

            if (notificationResponse.ok) {

                const notifications =
                    await notificationResponse.json();

                if (
                    Array.isArray(notifications)
                ) {

                    const sent =
                        notifications.filter(
                            notification =>
                                String(
                                    notification.status || ""
                                ).toUpperCase() === "SENT"
                        );

                    notificationsSent.textContent =
                        sent.length;
                }

            }

        } catch (error) {

            notificationsSent.textContent =
                "0";
        }


    } catch (error) {

        activeSubscribers.textContent =
            "0";

        notificationsSent.textContent =
            "0";
    }
}


// ============================================================
// LOAD INTERNSHIPS
// ============================================================

async function loadInternships() {

    showLoading();

    try {

        const userEmail =
            localStorage.getItem(
                "user_email"
            );

        const internshipsUrl =
            userEmail
                ? `${API_URL}/internships?user_email=${encodeURIComponent(userEmail)}`
                : `${API_URL}/internships`;

        const response =
            await fetch(
                internshipsUrl
            );

        if (!response.ok) {

            throw new Error(
                `Server returned ${response.status}`
            );
        }


        // ====================================================
        // GET REAL DATA FROM BACKEND
        // ====================================================

        const internships =
            await response.json();


        hideLoading();


        // ====================================================
        // EMPTY STATE
        // ====================================================

        if (
            !Array.isArray(internships) ||
            internships.length === 0
        ) {

            totalJobs.textContent =
                "0";

            emptyState.classList.remove(
                "hidden"
            );

            await loadAnalytics();

            return;
        }


        // ====================================================
        // TOTAL JOBS
        // ====================================================

        totalJobs.textContent =
            internships.length;


        // ====================================================
        // SORT NEWEST FIRST
        // ====================================================

        internships.sort(
            (a, b) => {

                const dateA =
                    new Date(
                        getDateValue(a) || 0
                    ).getTime();

                const dateB =
                    new Date(
                        getDateValue(b) || 0
                    ).getTime();

                return dateB - dateA;
            }
        );


        // ====================================================
        // DISPLAY
        // ====================================================

        displayInternships(
            internships
        );


        // ====================================================
        // ANALYTICS
        // ====================================================

        await loadAnalytics();


    } catch (error) {

        console.error(
            "Internship loading error:",
            error
        );

        hideLoading();

        errorMessage.textContent =
            error.message ||
            "Unable to connect to the backend.";

        errorState.classList.remove(
            "hidden"
        );
    }
}


// ============================================================
// DISPLAY INTERNSHIPS
// ============================================================

function displayInternships(internships) {

    internshipsContainer.innerHTML =
        "";

    internships.forEach(
        internship => {

            const card =
                document.createElement(
                    "article"
                );

            card.className =
                "internship-card";


            const score =
                getScore(
                    internship
                );

            const scoreClass =
                getScoreClass(
                    score
                );

            const scoreLabel =
                getScoreLabel(
                    score
                );


            const company =
                internship.company ||
                "Unknown Company";

            const title =
                internship.title ||
                "Internship Opportunity";

            const location =
                getLocation(
                    internship
                );

            const source =
                getSource(
                    internship
                );

            const relativeTime =
                getRelativeTime(
                    getDateValue(
                        internship
                    )
                );

            const applyUrl =
                getApplyUrl(
                    internship
                );


            card.innerHTML = `

                <div class="internship-card-top">

                    <div>

                        <h3 class="job-title">
                            🌐
                            ${escapeHtml(title)}
                        </h3>

                        <p class="job-company">
                            🏢
                            ${escapeHtml(company)}
                        </p>

                        <p class="job-location">
                            📍
                            ${escapeHtml(location)}
                        </p>

                    </div>

                    <div class="score-badge ${scoreClass}">
                        ${escapeHtml(scoreLabel)}
                    </div>

                </div>


                <div class="job-meta">

                    <span class="discovered">
                        ⏱️
                        ${escapeHtml(relativeTime)}
                    </span>

                </div>


                <div class="job-divider"></div>


                <div class="internship-card-bottom">

    <span class="source">
        🌐 via
        ${escapeHtml(source)}
    </span>


    <div class="internship-actions">

        ${
            applyUrl !== "#"

            ?

            `
            <a
                href="${escapeHtml(applyUrl)}"
                target="_blank"
                rel="noopener noreferrer"
                class="apply-button"
            >
                🚀 Apply Now
            </a>
            `

            :

            `
            <span
                class="apply-button disabled"
            >
                🔗 Link Unavailable
            </span>
            `
        }


        <button
            type="button"
            class="remove-button"
            onclick="removeInternship(${internship.id}, this)"
        >
            🗑️ Remove
        </button>

    </div>



            `;


            internshipsContainer.appendChild(
                card
            );

        }
    );
}
// ============================================================
// REMOVE INTERNSHIP
// ============================================================

async function removeInternship(
    internshipId,
    button
) {

    const userEmail =
        localStorage.getItem(
            "user_email"
        );

    if (
        !userEmail ||
        !internshipId
    ) {
        return;
    }


    button.disabled =
        true;

    button.textContent =
        "⏳ Removing...";


    try {

        const response =
            await fetch(
                `${API_URL}/internships/${internshipId}/dismiss`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        user_email: userEmail
                    })
                }
            );


        if (!response.ok) {

            throw new Error(
                `Server returned ${response.status}`
            );
        }


        // Reload dashboard so the
        // dismissed internship disappears.

        await loadInternships();


    } catch (error) {

        console.error(
            "Remove internship error:",
            error
        );

        button.disabled =
            false;

        button.textContent =
            "🗑️ Remove";

        alert(
            "Unable to remove this internship. Please try again."
        );
    }
}

// ============================================================
// REFRESH BUTTON
// ============================================================

refreshButton.addEventListener(
    "click",
    async function() {

        refreshButton.disabled =
            true;

        refreshButton.textContent =
            "⏳ Refreshing...";

        await loadInternships();

        refreshButton.disabled =
            false;

        refreshButton.textContent =
            "🔄 Refresh";
    }
);


// ============================================================
// RETRY BUTTON
// ============================================================

retryButton.addEventListener(
    "click",
    loadInternships
);


// ============================================================
// INITIAL LOAD
// ============================================================

loadInternships();