// ============================================================
// API
// ============================================================

const API_URL = window.location.origin;


// ============================================================
// DOM ELEMENTS
// ============================================================

const subscriptionForm =
    document.getElementById(
        "subscriptionForm"
    );


const subscriptionsContainer =
    document.getElementById(
        "subscriptions"
    );


const message =
    document.getElementById(
        "message"
    );


const refreshButton =
    document.getElementById(
        "refreshButton"
    );


const addButton =
    document.getElementById(
        "addButton"
    );


const radarStatus =
    document.getElementById(
        "radarStatus"
    );


// ============================================================
// ESCAPE HTML
// ============================================================

function escapeHtml(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return "";

    }


    return String(value)

        .replace(
            /&/g,
            "&amp;"
        )

        .replace(
            /</g,
            "&lt;"
        )

        .replace(
            />/g,
            "&gt;"
        )

        .replace(
            /"/g,
            "&quot;"
        )

        .replace(
            /'/g,
            "&#039;"
        );

}


// ============================================================
// SHOW MESSAGE
// ============================================================

function showMessage(
    text,
    type
) {

    message.textContent = text;

    message.className =
        "message " + type;

}


// ============================================================
// UPDATE RADAR COUNT
// ============================================================

function updateRadarCount(
    trackers
) {

    if (!radarStatus) {

        return;

    }


    const count =
        Array.isArray(trackers)
            ? trackers.length
            : 0;


    if (count === 0) {

        radarStatus.innerHTML = `
            <span class="pulse-dot">●</span>
            0 Active Radars Scanning...
        `;

    }

    else if (count === 1) {

        radarStatus.innerHTML = `
            <span class="pulse-dot">●</span>
            1 Active Radar Scanning...
        `;

    }

    else {

        radarStatus.innerHTML = `
            <span class="pulse-dot">●</span>
            ${count} Active Radars Scanning...
        `;

    }

}


// ============================================================
// LOAD SUBSCRIPTIONS
// ============================================================

async function loadSubscriptions() {

    try {

        subscriptionsContainer.innerHTML = `
            <div class="empty-trackers">

                <div class="empty-icon">
                    ⏳
                </div>

                <h3>
                    Loading trackers...
                </h3>

                <p>
                    Connecting to the tracking database.
                </p>

            </div>
        `;


        const userEmail =
    localStorage.getItem("user_email");

if (!userEmail) {

    displaySubscriptions([]);

    return;

}

const response =
    await fetch(
        `${API_URL}/subscriptions?user_email=${encodeURIComponent(userEmail)}`
    );


        if (!response.ok) {

            throw new Error(
                "Unable to load trackers."
            );

        }


        const subscriptions =
            await response.json();


        displaySubscriptions(
            Array.isArray(subscriptions)
                ? subscriptions
                : []
        );


    }

    catch (error) {

        updateRadarCount([]);


        subscriptionsContainer.innerHTML = `
            <div class="empty-trackers">

                <div class="empty-icon">
                    ⚠️
                </div>

                <h3>
                    Unable to load trackers
                </h3>

                <p>
                    ${escapeHtml(
                        error.message
                    )}
                </p>

            </div>
        `;

    }

}


// ============================================================
// DISPLAY SUBSCRIPTIONS
// ============================================================

function displaySubscriptions(
    subscriptions
) {
    subscriptions =
    subscriptions.filter(
        subscription =>
            subscription.status !== "CANCELLED"
    );

    // Count ONLY active trackers
    const activeTrackers =
        subscriptions.filter(
            subscription =>
                subscription.is_active === true
        );

    updateRadarCount(
        activeTrackers
    );


    // --------------------------------------------------------
    // NO TRACKERS
    // --------------------------------------------------------

    if (
        !subscriptions ||
        subscriptions.length === 0
    ) {

        subscriptionsContainer.innerHTML = `

            <div class="empty-trackers">

                <div class="empty-icon">
                    📡
                </div>

                <h3>
                    No trackers yet
                </h3>

                <p>
                    Enter your email and target company
                    to fire up your first tracking agent.
                </p>

            </div>

        `;

        return;

    }


    // --------------------------------------------------------
    // CLEAR OLD CARDS
    // --------------------------------------------------------

    subscriptionsContainer.innerHTML = "";


    // --------------------------------------------------------
    // CREATE CARDS
    // --------------------------------------------------------

    subscriptions.forEach(
        subscription => {

            const card =
                document.createElement(
                    "div"
                );


            card.className =
                "tracker-card";


            const company =
                escapeHtml(
                    subscription.company
                );


            const domain =
                escapeHtml(
                    subscription.domain ||
                    "All Internships"
                );


            // ------------------------------------------------
            // ACTIVE / PAUSED BUTTON
            // ------------------------------------------------

            const actionButton =
                subscription.is_active === true

                    ? `
                        <button
                            class="pause-button"
                            type="button"
                            onclick="pauseTracker(
                                ${subscription.id}
                            )"
                        >
                            ⏸️ Pause
                        </button>
                    `

                    : `
                        <button
                            class="resume-button"
                            type="button"
                            onclick="resumeTracker(
                                ${subscription.id}
                            )"
                        >
                            ▶️ Resume
                        </button>
                    `;


            // ------------------------------------------------
            // STATUS
            // ------------------------------------------------

            const status =
                subscription.is_active === true

                    ? `
                        <span>
                            🟢 Active
                        </span>
                    `

                    : `
                        <span>
                            ⏸️ Paused
                        </span>
                    `;


            card.innerHTML = `

                <div class="tracker-details">

                    <h3>
                        🏢 ${company}
                    </h3>

                    <p>
                        🔍 Focus: ${domain}
                    </p>

                    <p>
                        ${status}
                    </p>

                </div>


                <div class="tracker-actions">

                    ${actionButton}


                    <button
                        class="delete-button"
                        type="button"
                        onclick="deleteTracker(
                            ${subscription.id}
                        )"
                    >
                        🗑️ Delete
                    </button>

                </div>

            `;


            subscriptionsContainer.appendChild(
                card
            );

        }
    );

}


// ============================================================
// ADD SUBSCRIPTION
// ============================================================

subscriptionForm.addEventListener(
    "submit",
    async function(event) {

        event.preventDefault();


        // ----------------------------------------------------
        // GET VALUES
        // ----------------------------------------------------

        const email =
            document
                .getElementById("email")
                .value
                .trim();


        const company =
            document
                .getElementById("company")
                .value
                .trim();


        const domain =
            document
                .getElementById("domain")
                .value
                .trim();


        // ----------------------------------------------------
        // BASIC VALIDATION
        // ----------------------------------------------------

        if (!email) {

            showMessage(
                "❌ Please enter your email address.",
                "error"
            );

            return;

        }


        if (!company) {

            showMessage(
                "❌ Please enter a target company.",
                "error"
            );

            return;

        }


        // ----------------------------------------------------
        // LOADING STATE
        // ----------------------------------------------------

        addButton.disabled = true;

        addButton.textContent =
            "⏳ Connecting to Agent...";


        message.className =
            "message";


        try {


            // ------------------------------------------------
            // SEND TO FASTAPI
            // ------------------------------------------------

            const response =
                await fetch(
                    `${API_URL}/subscriptions`,
                    {

                        method: "POST",

                        headers: {

                            "Content-Type":
                                "application/json"

                        },

                        body: JSON.stringify({

                            user_email: email,

                            company: company,

                            domain:
                                domain || null

                        })

                    }
                );


            // ------------------------------------------------
            // READ RESPONSE SAFELY
            // ------------------------------------------------

            const data =
                await response.json();


            // ------------------------------------------------
            // HANDLE ERROR
            // ------------------------------------------------

            if (!response.ok) {

                let errorMessage =
                    "Failed to activate tracking.";


                if (
                    data &&
                    data.detail
                ) {

                    if (
                        Array.isArray(
                            data.detail
                        )
                    ) {

                        errorMessage =
                            data.detail
                                .map(
                                    error => {

                                        if (
                                            typeof error ===
                                            "object" &&
                                            error.msg
                                        ) {

                                            return error.msg;

                                        }

                                        return String(
                                            error
                                        );

                                    }
                                )
                                .join(", ");

                    }

                    else if (
                        typeof data.detail ===
                        "string"
                    ) {

                        errorMessage =
                            data.detail;

                    }

                    else {

                        errorMessage =
                            JSON.stringify(
                                data.detail
                            );

                    }

                }


                throw new Error(
                    errorMessage
                );

            }


            // ------------------------------------------------
// SUCCESS
// ------------------------------------------------

localStorage.setItem(
    "user_email",
    email
);
            

showMessage(
    "Automated radar activated successfully!",
    "success"
);


            // ------------------------------------------------
            // CLEAR FORM
            // ------------------------------------------------

            subscriptionForm.reset();


            // ------------------------------------------------
            // RELOAD TRACKERS
            // ------------------------------------------------

            await loadSubscriptions();


        }

        catch (error) {

            console.error(
                "Subscription error:",
                error
            );


            showMessage(
                `❌ ${error.message}`,
                "error"
            );

        }


        finally {

            // ------------------------------------------------
            // RESTORE BUTTON
            // ------------------------------------------------

            addButton.disabled =
                false;

            addButton.textContent =
                "⚡ Activate Automated Radar";

        }

    }
);


// ============================================================
// DELETE TRACKER
// ============================================================
async function pauseTracker(
    subscriptionId
) {

    if (!subscriptionId) {

        return;

    }


    try {

        const response =
            await fetch(
                `${API_URL}/subscriptions/${subscriptionId}/pause`,
                {
                    method: "PATCH"
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Failed to pause tracker."
            );

        }


        showMessage(
            "⏸️ Tracking agent paused successfully.",
            "success"
        );


        await loadSubscriptions();

    }

    catch (error) {

        console.error(
            "Pause error:",
            error
        );


        showMessage(
            `❌ ${error.message}`,
            "error"
        );

    }

}
async function resumeTracker(
    subscriptionId
) {

    if (!subscriptionId) {

        return;

    }


    try {

        const response =
            await fetch(
                `${API_URL}/subscriptions/${subscriptionId}/resume`,
                {
                    method: "PATCH"
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Failed to resume tracker."
            );

        }


        showMessage(
            "▶️ Tracking agent resumed successfully.",
            "success"
        );


        await loadSubscriptions();

    }

    catch (error) {

        console.error(
            "Resume error:",
            error
        );


        showMessage(
            `❌ ${error.message}`,
            "error"
        );

    }

}
async function deleteTracker(
    subscriptionId
) {

    if (!subscriptionId) {

        return;

    }


    const confirmed =
        window.confirm(
            "Are you sure you want to stop this tracking agent?"
        );


    if (!confirmed) {

        return;

    }


    try {

        const response =
            await fetch(
                `${API_URL}/subscriptions/${subscriptionId}`,
                {

                    method: "DELETE"

                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Failed to delete tracker."
            );

        }


        showMessage(
            "✅ Tracking agent stopped successfully.",
            "success"
        );


        // ----------------------------------------------------
        // IMPORTANT:
        // Reloading causes the radar count to update.
        // ----------------------------------------------------

        await loadSubscriptions();


    }

    catch (error) {

        console.error(
            "Delete error:",
            error
        );


        showMessage(
            `❌ ${error.message}`,
            "error"
        );

    }

}


// ============================================================
// REFRESH BUTTON
// ============================================================

if (refreshButton) {

    refreshButton.addEventListener(
        "click",
        async function() {

            refreshButton.disabled =
                true;


            refreshButton.textContent =
                "⏳";


            await loadSubscriptions();


            refreshButton.disabled =
                false;


            refreshButton.textContent =
                "🔄";

        }
    );

}


// ============================================================
// INITIAL LOAD
// ============================================================

loadSubscriptions();