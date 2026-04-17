import React, { useState } from 'react';
import { LogIn, Mail, Lock } from 'lucide-react';
import { loginUser, claimDevice } from '../services/api';

const Login = ({ onLoginSuccess }) => {
	const [email, setEmail] = useState('');
	const [password, setPassword] = useState('');
	const [error, setError] = useState('');
	const [isSubmitting, setIsSubmitting] = useState(false);

	const handleSubmit = async (e) => {
		e.preventDefault();
		setError('');
		setIsSubmitting(true);

		try {
			const user = await loginUser(email, password);
            // Báo cho backend biết User này đang sở hữu thiết bị
            await claimDevice(user.user_id, 'device_0001');
            
			onLoginSuccess(user);
		} catch (err) {
			setError(err.message || 'Login failed');
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="min-h-screen bg-background flex items-center justify-center px-6">
			<div className="w-full max-w-md bg-card rounded-3xl shadow-sm border border-gray-100 p-8">
				<div className="mb-8 text-center">
					<div className="w-14 h-14 mx-auto rounded-2xl bg-primary/15 flex items-center justify-center text-primary mb-4">
						<LogIn size={26} strokeWidth={2} />
					</div>
					<h1 className="text-3xl font-semibold text-textMain">HERA Login</h1>
					<p className="text-textMuted mt-2">
						Sign in with your HERA account to access the dashboard
					</p>
				</div>

				<form onSubmit={handleSubmit} className="space-y-5">
					<div>
						<label className="block text-sm font-medium text-textMain mb-2">
							Email
						</label>
						<div className="flex items-center gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3">
							<Mail size={18} className="text-textMuted" />
							<input
								type="email"
								value={email}
								onChange={(e) => setEmail(e.target.value)}
								placeholder="you@hera.com"
								className="w-full bg-transparent outline-none text-textMain placeholder:text-textMuted"
								required
							/>
						</div>
					</div>

					<div>
						<label className="block text-sm font-medium text-textMain mb-2">
							Password
						</label>
						<div className="flex items-center gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3">
							<Lock size={18} className="text-textMuted" />
							<input
								type="password"
								value={password}
								onChange={(e) => setPassword(e.target.value)}
								placeholder="Enter your password"
								className="w-full bg-transparent outline-none text-textMain placeholder:text-textMuted"
								required
							/>
						</div>
					</div>

					{error ? (
						<div className="rounded-2xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
							{error}
						</div>
					) : null}

					<button
						type="submit"
						disabled={isSubmitting}
						className="w-full rounded-2xl bg-primary text-white py-3.5 font-medium transition hover:opacity-90 disabled:opacity-60"
					>
						{isSubmitting ? 'Signing in...' : 'Sign in'}
					</button>
				</form>

				<div className="mt-6 rounded-2xl bg-background px-4 py-3 text-sm text-textMuted">
					Test account: <span className="text-textMain font-medium">neji.kareshi@hera.com</span>
				</div>
			</div>
		</div>
	);
};

export default Login;