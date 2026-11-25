CREATE TABLE bookings (
    id INTEGER PRIMARY KEY,
    plot_id INTEGER NOT NULL REFERENCES plots (id),
    member_id INTEGER NOT NULL REFERENCES members (id),
    season TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'cancelled')),
    price_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    cancelled_at TEXT
);

CREATE INDEX bookings_plot_season ON bookings (plot_id, season, status);
