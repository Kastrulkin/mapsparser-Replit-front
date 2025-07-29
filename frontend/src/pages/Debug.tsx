import React, { useState } from 'react';
import { SupabaseDebug } from '../lib/supabaseDebug';
import { AuthTester } from '../lib/authTest';
import { supabase } from '../lib/supabase';

const Debug: React.FC = () => {
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const addResult = (title: string, data: any) => {
    setResults(prev => [...prev, { title, data, timestamp: new Date().toISOString() }]);
  };

  const testAuthStatus = async () => {
    setLoading(true);
    try {
      const result = await SupabaseDebug.checkAuthStatus();
      addResult('Auth Status', result);
    } catch (error) {
      addResult('Auth Status Error', error);
    } finally {
      setLoading(false);
    }
  };

  const testSignUp = async () => {
    setLoading(true);
    try {
      const result = await AuthTester.testSignUp();
      addResult('Test SignUp', result);
    } catch (error) {
      addResult('Test SignUp Error', error);
    } finally {
      setLoading(false);
    }
  };

  const testEmailSettings = async () => {
    setLoading(true);
    try {
      const result = await AuthTester.checkSupabaseConfig();
      addResult('Supabase Config', result);
    } catch (error) {
      addResult('Supabase Config Error', error);
    } finally {
      setLoading(false);
    }
  };

  const testDatabase = async () => {
    setLoading(true);
    try {
      const { data, error } = await supabase
        .from('Users')
        .select('*')
        .limit(5);
      
      addResult('Database Test', { data, error });
    } catch (error) {
      addResult('Database Test Error', error);
    } finally {
      setLoading(false);
    }
  };

  const testPasswordReset = async () => {
    setLoading(true);
    try {
      const result = await AuthTester.testPasswordReset('demyanovp@yandex.ru');
      addResult('Password Reset Test', result);
    } catch (error) {
      addResult('Password Reset Error', error);
    } finally {
      setLoading(false);
    }
  };

  const testRateLimit = async () => {
    setLoading(true);
    try {
      const results = await AuthTester.testRateLimit(2);
      addResult('Rate Limit Test', results);
    } catch (error) {
      addResult('Rate Limit Error', error);
    } finally {
      setLoading(false);
    }
  };

  const runFullAuthTest = async () => {
    setLoading(true);
    try {
      const results = await AuthTester.runFullAuthTest();
      addResult('Full Auth Test Suite', results);
    } catch (error) {
      addResult('Full Auth Test Error', error);
    } finally {
      setLoading(false);
    }
  };

  const clearResults = () => {
    setResults([]);
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Supabase Debug Panel</h1>
      
      <div className="grid grid-cols-2 gap-4 mb-6">
        <button
          onClick={testAuthStatus}
          disabled={loading}
          className="bg-blue-500 text-white p-3 rounded disabled:opacity-50"
        >
          Test Auth Status
        </button>
        
        <button
          onClick={testSignUp}
          disabled={loading}
          className="bg-green-500 text-white p-3 rounded disabled:opacity-50"
        >
          Test SignUp
        </button>
        
        <button
          onClick={testEmailSettings}
          disabled={loading}
          className="bg-yellow-500 text-white p-3 rounded disabled:opacity-50"
        >
          Supabase Config
        </button>
        
        <button
          onClick={testDatabase}
          disabled={loading}
          className="bg-purple-500 text-white p-3 rounded disabled:opacity-50"
        >
          Test Database
        </button>

        <button
          onClick={testPasswordReset}
          disabled={loading}
          className="bg-orange-500 text-white p-3 rounded disabled:opacity-50"
        >
          Test Password Reset
        </button>

        <button
          onClick={testRateLimit}
          disabled={loading}
          className="bg-red-500 text-white p-3 rounded disabled:opacity-50"
        >
          Test Rate Limit
        </button>

        <button
          onClick={runFullAuthTest}
          disabled={loading}
          className="bg-indigo-500 text-white p-3 rounded disabled:opacity-50 col-span-2"
        >
          🚀 Run Full Auth Test Suite
        </button>
      </div>

      <button
        onClick={clearResults}
        className="bg-red-500 text-white p-2 rounded mb-4"
      >
        Clear Results
      </button>

      <div className="space-y-4">
        {results.map((result, index) => (
          <div key={index} className="border p-4 rounded">
            <h3 className="font-bold mb-2">{result.title}</h3>
            <p className="text-sm text-gray-500 mb-2">{result.timestamp}</p>
            <pre className="bg-gray-100 p-2 rounded text-xs overflow-auto">
              {JSON.stringify(result.data, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Debug; 