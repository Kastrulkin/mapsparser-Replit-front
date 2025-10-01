import { useEffect, useState } from 'react';
import { newAuth } from '@/lib/auth_new';
import { useNavigate, useLocation } from 'react-router-dom';
import Hero from '@/components/Hero';
import Features from '@/components/Features';
import Stats from '@/components/Stats';
import Testimonials from '@/components/Testimonials';
import CTA from '@/components/CTA';
import Footer from '@/components/Footer';

const Index = () => {
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Проверяем авторизацию при загрузке страницы
    const checkAuth = async () => {
      try {
        const user = await newAuth.getCurrentUser();
        if (user) {
          // Если пользователь авторизован, перенаправляем в личный кабинет
          navigate('/dashboard');
          return;
        }
      } catch (error) {
        console.log('User not authenticated');
      }
      setLoading(false);
    };

    checkAuth();
  }, [navigate]);

  // Обработка хэшей для навигации
  useEffect(() => {
    if (location.hash === "#agents" || location.hash === "#cta") {
      const el = document.getElementById(location.hash.replace('#', ''));
      if (el) {
        setTimeout(() => {
          el.scrollIntoView({ behavior: "smooth" });
        }, 100);
      }
    }
  }, [location]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p>Загрузка...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Hero />
      <Features />
      <Stats />
      <Testimonials />
      <CTA />
      <Footer />
    </div>
  );
};

export default Index;
