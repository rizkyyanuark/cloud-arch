-- PostgreSQL Trigger for Seamless New User Onboarding
-- Automatically sets password to MiniProject2026! and marks it expired for mandatory reset on first sign-in.

CREATE OR REPLACE FUNCTION fn_auto_setup_new_user_password()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.user_type = 0 AND (NEW.encrypted_password IS NULL OR NEW.encrypted_password = '') THEN
        NEW.encrypted_password := '$2a$13$geTFs3nY3W8/3QIg6WgBF.W3yFKqjXVH8N/Ao6c1p/5.gKUjX3.oe'; -- MiniProject2026!
        NEW.password_automatically_set := false;
        NEW.password_expires_at := NOW() - INTERVAL '1 minute';
        IF NEW.confirmed_at IS NULL THEN
            NEW.confirmed_at := NOW();
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auto_setup_new_user ON users;
CREATE TRIGGER trg_auto_setup_new_user
BEFORE INSERT ON users
FOR EACH ROW
EXECUTE FUNCTION fn_auto_setup_new_user_password();
