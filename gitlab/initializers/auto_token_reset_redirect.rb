# Seamless Password Reset Redirection Hook
# Intercepts users with expired/default passwords and redirects directly to token edit page.

ActiveSupport.on_load(:action_controller_base) do
  ApplicationController.class_eval do
    def check_password_expiration
      return if session[:impersonator_id]
      return if current_user.nil?

      if current_user.password_expired? && current_user.allow_password_authentication?
        raw_token, enc_token = Devise.token_generator.generate(User, :reset_password_token)
        current_user.update_columns(reset_password_token: enc_token, reset_password_sent_at: Time.now.utc)
        sign_out(current_user)
        redirect_to edit_user_password_path(reset_password_token: raw_token)
      end
    end
  end
end
