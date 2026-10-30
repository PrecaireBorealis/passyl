-- spec 7.4 (frozen contract)
DROP TABLE IF EXISTS localities, merchants, merchant_policy, products, customers, transactions, hourly,
  weather_hourly, festivals, disruptions, actions, action_targets, audit_log, merchant_memory,
  past_campaigns, shock_labels CASCADE;

-- reference
CREATE TABLE localities(id text PRIMARY KEY, city text, name text, lat float, lon float);
CREATE TABLE merchants(id text PRIMARY KEY, name text, category text, locality_id text, lat float, lon float,
                       opened_on date, language text DEFAULT 'hi-en');
CREATE TABLE merchant_policy(merchant_id text PRIMARY KEY, price_band_pct float DEFAULT 10,
                             margin_floor_pct float DEFAULT 20, daily_offer_budget int DEFAULT 300,
                             quiet_after_hour int DEFAULT 22, autonomy_level text DEFAULT 'L2',
                             allow_price_changes bool DEFAULT true);
CREATE TABLE products(id text PRIMARY KEY, merchant_id text, name text, category text, mrp int, price int, cost int,
                      is_combo bool DEFAULT false);
CREATE TABLE customers(payer_hash text, merchant_id text, first_seen date, is_regular bool, opted_in bool,
                       PRIMARY KEY(payer_hash, merchant_id));

-- facts
CREATE TABLE transactions(txn_id text PRIMARY KEY, merchant_id text, ts timestamptz, amount int, payer_hash text,
                          status text, product_id text NULL);
CREATE TABLE hourly(merchant_id text, date date, hour int, revenue int, txns int, success_txns int,
                    regular_txns int, new_txns int, unique_payers int, PRIMARY KEY(merchant_id, date, hour));

-- context (real + synthetic)
CREATE TABLE weather_hourly(locality_id text, ts timestamptz, precip_mm float, temp_c float, source text);
CREATE TABLE festivals(date date, name text, scope text, source text);
CREATE TABLE disruptions(city text, date date, kind text, severity float, source text DEFAULT 'synthetic');

-- app state
CREATE TABLE actions(id text PRIMARY KEY, merchant_id text, kind text, params jsonb, status text,
                     created_at timestamptz, window_start timestamptz, window_end timestamptz,
                     expected jsonb, policy jsonb);
CREATE TABLE action_targets(action_id text, payer_hash text, arm text, returned bool NULL, spend int NULL);
CREATE TABLE audit_log(id serial PRIMARY KEY, ts timestamptz, merchant_id text, actor text, event text, payload jsonb);
CREATE TABLE merchant_memory(merchant_id text, key text, value jsonb, updated_at timestamptz,
                             PRIMARY KEY(merchant_id, key));
CREATE TABLE past_campaigns(id text PRIMARY KEY, merchant_id text, kind text, category text, n_treat int, n_hold int,
                            treat_rate float, hold_rate float, date date);

-- hidden from the engine (benchmark only)
CREATE TABLE shock_labels(id text PRIMARY KEY, merchant_id text NULL, city text NULL, date date, start_hour int,
                          end_hour int, kind text, true_effect_pct float, scope text);
