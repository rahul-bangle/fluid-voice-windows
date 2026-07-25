import React, { useState, useEffect } from 'react';
import { 
  Home, 
  BarChart3, 
  BookOpen, 
  Settings, 
  Code, 
  Wand2, 
  FileEdit, 
  Users, 
  HelpCircle, 
  Copy, 
  Search, 
  ArrowRight, 
  X,
  Volume2,
  Mic,
  Key,
  Database,
  User,
  Shield,
  Sparkles,
  Zap,
  Target,
  Clock,
  Mail,
  MessageSquare,
  FileText,
  RotateCw
} from 'lucide-react';

const INITIAL_SNIPPETS = [
  {
    id: 1,
    title: "my VeloVoice referral",
    body: "Hey, use my referral link to get 1 month off VeloVoice Pro! https://velovoice.ai/r?RAHUL1"
  },
  {
    id: 2,
    title: "my email address",
    body: "bangleahul1@gmail.com"
  },
  {
    id: 3,
    title: "organize thoughts prompt",
    body: "Organize these unstructured thoughts into a clear, polished version without adding or removing intent..."
  }
];

const MOCK_ANALYTICS = {
  total_dictations: 1,
  total_words: 8,
  avg_wpm: 150.0,
  total_time_saved_mins: 0.2,
  avg_stt_ms: 210,
  avg_llm_ms: 640,
  avg_paste_ms: 2.0,
  avg_total_ms: 852.0,
  total_fixes: 1
};

export default function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [history, setHistory] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  const [analytics, setAnalytics] = useState(MOCK_ANALYTICS);
  const [vocabulary, setVocabulary] = useState([]);
  const [snippets, setSnippets] = useState(INITIAL_SNIPPETS);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState('general');
  const [snippetModal, setSnippetModal] = useState({ isOpen: false, snippet: null });

  // Settings State Management
  const [settingsState, setSettingsState] = useState({
    hotkey: 'Ctrl+Shift',
    micDevice: 'Default Microphone',
    groqApiKey: 'gsk_********************************',
    sttModel: 'whisper-large-v3-turbo (Groq Cloud)',
    llmFixMode: 'Hinglish Auto-Fix (Recommended)',
    autostart: true,
    sfxEnabled: true,
    directInjection: true
  });

  const refreshDashboardData = () => {
    try {
      if (window.pyqtBridge) {
        const histJson = typeof window.pyqtBridge.getHistory === 'function' ? window.pyqtBridge.getHistory() : null;
        if (histJson) setHistory(JSON.parse(histJson));
        
        const analyticsJson = typeof window.pyqtBridge.getAnalyticsSummary === 'function' ? window.pyqtBridge.getAnalyticsSummary() : null;
        if (analyticsJson) setAnalytics(JSON.parse(analyticsJson));
        
        const vocabJson = typeof window.pyqtBridge.getVocabulary === 'function' ? window.pyqtBridge.getVocabulary() : null;
        if (vocabJson) setVocabulary(JSON.parse(vocabJson));
      } else if (window.qt && window.qt.webChannelTransport) {
        // Fallback for QWebChannel async initialization
        if (!window.pyqtChannelSetup) {
          window.pyqtChannelSetup = true;
          new window.QWebChannel(window.qt.webChannelTransport, function(channel) {
            window.pyqtBridge = channel.objects.pyqtBridge;
            refreshDashboardData();
          });
        }
      }
    } catch (e) {
      console.error("Failed to load PyQT bridge data:", e);
    }
  };

  // Sync with PyQT bridge and set up poll timer for live auto-refresh
  useEffect(() => {
    refreshDashboardData();
    const interval = setInterval(refreshDashboardData, 2000);
    return () => clearInterval(interval);
  }, []);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const handleSaveSettings = () => {
    if (window.pyqtBridge && typeof window.pyqtBridge.saveSettings === 'function') {
      try {
        const payload = {
          hotkey: settingsState.hotkey,
          mic_device: settingsState.micDevice,
          api_key: settingsState.groqApiKey,
          stt_model: settingsState.sttModel,
          llm_fix_mode: settingsState.llmFixMode,
          autostart: settingsState.autostart,
          sfx_enabled: settingsState.sfxEnabled,
          direct_injection: settingsState.directInjection
        };
        window.pyqtBridge.saveSettings(JSON.stringify(payload));
      } catch (e) {
        console.error("Failed to save settings via PyQT Bridge:", e);
      }
    }
    setIsSettingsOpen(false);
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex font-sans bg-[#F7F9FB] text-slate-800 selection:bg-blue-100">
      
      {/* 1. LEFT SIDEBAR (1:1 Match with Stitch Light Theme) */}
      <aside className="w-64 border-r border-[#E2E8F0] bg-white flex flex-col h-full shrink-0">
        {/* Brand Logo Header */}
        <div className="p-6 flex items-center space-x-3">
          <img 
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuDnegORGWT9zPG5b4H-7NL1r6yg375yTBCxG-V4Wu4wz25Gx0hjSTAmUEstDz6OgQA3b0zFY9WckRxV5wttkA2zK2gR55PqAde4-ZKOh0CuxVS7lH_vwdEOx2_4vuF_ipZe6O7qeaMRRlpuwDM85vgjgRhEmw1HEtUVH2KHiO2lareINmrv4UOiQe8vl-n1T7rHDkuDz54cyOm0mLTV8JOvRy4Z3uFFoeZ9vZdOg4Si9BudJM_FhLAMU0dEeLDWGwpjNp9bXTKJhgY" 
            alt="Velo AI Logo" 
            className="w-8 h-8 rounded-md"
          />
          <span className="font-bold text-xl tracking-tight text-[#1E293B]">Velo AI</span>
          <span className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-bold border border-blue-100 uppercase">PRO</span>
        </div>

        {/* Navigation Section */}
        <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
          <button 
            onClick={() => setActiveTab('home')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-colors ${activeTab === 'home' ? 'bg-blue-50 text-blue-600 font-semibold' : 'text-[#64748B] hover:bg-gray-50 hover:text-[#1E293B]'}`}
          >
            <Home className="w-5 h-5" />
            <span>Home</span>
          </button>
          
          <button 
            onClick={() => setActiveTab('insights')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-colors ${activeTab === 'insights' ? 'bg-blue-50 text-blue-600 font-semibold' : 'text-[#64748B] hover:bg-gray-50 hover:text-[#1E293B]'}`}
          >
            <BarChart3 className="w-5 h-5" />
            <span>Insights</span>
          </button>

          <button 
            onClick={() => setActiveTab('dictionary')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-colors ${activeTab === 'dictionary' ? 'bg-blue-50 text-blue-600 font-semibold' : 'text-[#64748B] hover:bg-gray-50 hover:text-[#1E293B]'}`}
          >
            <BookOpen className="w-5 h-5" />
            <span>Dictionary</span>
          </button>

          <button 
            onClick={() => setActiveTab('snippets')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-colors ${activeTab === 'snippets' ? 'bg-blue-50 text-blue-600 font-semibold' : 'text-[#64748B] hover:bg-gray-50 hover:text-[#1E293B]'}`}
          >
            <Code className="w-5 h-5" />
            <span>Snippets</span>
          </button>

          {/* Stitch Purple Plan Banner */}
          <div className="mt-8 p-4 bg-purple-50 rounded-xl border border-purple-100">
            <p className="text-xs font-bold text-purple-700 uppercase tracking-wider mb-1">Unlimited Usage</p>
            <p className="text-sm text-purple-900 font-medium">Pro plan active</p>
            <p className="text-[11px] text-purple-600 mt-2">You have priority access to all Velo AI models.</p>
            <button className="mt-3 w-full py-2 bg-purple-600 text-white text-xs font-bold rounded-lg hover:bg-purple-700 transition-colors shadow-sm">
              Manage Plan
            </button>
          </div>
        </nav>

        {/* Footer Sidebar */}
        <div className="p-4 border-t border-[#E2E8F0] space-y-1">
          <button className="w-full flex items-center space-x-3 px-3 py-2 text-[#64748B] hover:text-[#1E293B] text-sm">
            <Users className="w-4 h-4" />
            <span>Invite your team</span>
          </button>

          <button 
            onClick={() => setIsSettingsOpen(true)}
            className="w-full flex items-center space-x-3 px-3 py-2 text-[#64748B] hover:text-[#1E293B] text-sm"
          >
            <Settings className="w-4 h-4" />
            <span>Settings</span>
          </button>

          <button className="w-full flex items-center space-x-3 px-3 py-2 text-[#64748B] hover:text-[#1E293B] text-sm">
            <HelpCircle className="w-4 h-4" />
            <span>Help Center</span>
          </button>
        </div>
      </aside>

      {/* 2. DYNAMIC MAIN CONTENT VIEW AREA (Light Mode Theme) */}
      <main className="flex-1 overflow-y-auto bg-[#F7F9FB] p-8">
        
        {/* TAB 1: HOME VIEW (Pixel-Perfect Match with Stitch Dashboard Light Mode) */}
        {activeTab === 'home' && (
          <div className="max-w-6xl mx-auto space-y-8">
            {/* Header Section */}
            <header className="flex justify-between items-center mb-10">
              <h1 className="text-2xl font-bold text-[#1E293B]">
                Hey Rahul, <span className="text-[#64748B] font-normal">ready for your next session?</span>
              </h1>
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2 bg-orange-100 text-orange-700 px-3 py-1.5 rounded-lg border border-orange-200">
                  <span className="text-xs font-bold px-1.5 py-0.5 bg-orange-200 rounded">Ctrl</span>
                  <span className="text-xs">+</span>
                  <span className="text-xs font-bold px-1.5 py-0.5 bg-orange-200 rounded">Shift</span>
                </div>
                <button className="p-2 text-[#64748B] hover:text-[#1E293B] transition-colors">
                  <User className="w-6 h-6" />
                </button>
              </div>
            </header>

            <div className="flex flex-col lg:flex-row gap-8">
              {/* Main Column */}
              <div className="flex-1 space-y-8">
                {/* Hero Card */}
                <section className="relative h-64 rounded-2xl overflow-hidden bg-[#1E293B] shadow-xl p-8 flex flex-col justify-center">
                  <img 
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuBjNAZWkjxu9ZNCxLixB7WoOREy7rs9S5TGX1ZE4LsI1PrDS41JinlJoenAK4AaPuIb8ivfQncLSiZQQs_n4q-AchzyChNq1HLeundbnWeJTY_JuqNA_B75xTDjFFD78JC_7cytA7PiyvW9II665GmEFfA3arcpudPJjpkeienf3qvy1jr1O_Ihk2i3EwnFFt0mN7FVZ89gLfTU2JrC-3Yohk5iVZMBuovO6AEE4OD7fD76Jo1yBGWgHJSkbH2u5YyzM7n8bsAtX6M" 
                    alt="Flow Environment" 
                    className="absolute inset-0 w-full h-full object-cover opacity-60"
                  />
                  <div className="relative z-20 max-w-lg">
                    <h2 className="text-3xl font-bold text-white leading-tight mb-2">Unlock deep flow with Velo AI</h2>
                    <p className="text-gray-300 mb-6">Experience frictionless dictation that understands your context and technical vocabulary.</p>
                    <button className="bg-white text-[#1E293B] px-6 py-2.5 rounded-xl font-bold hover:bg-gray-100 transition-all shadow-lg inline-flex items-center space-x-2">
                      <span>Try Velo Voice</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>
                </section>

                {/* Activity Feed */}
                <section>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xs font-bold text-[#64748B] uppercase tracking-widest">RECENT DICTATIONS</h3>
                    <button 
                      onClick={refreshDashboardData}
                      className="p-1.5 text-[#64748B] hover:text-blue-600 hover:bg-white rounded-lg border border-transparent hover:border-[#E2E8F0] transition-colors shadow-sm inline-flex items-center gap-1 text-xs font-semibold"
                      title="Refresh dictations and analytics feed"
                    >
                      <RotateCw className="w-3.5 h-3.5" />
                      <span>Refresh</span>
                    </button>
                  </div>

                  {history.length === 0 ? (
                    <div className="bg-white rounded-2xl border border-[#E2E8F0] p-8 text-center text-[#64748B] shadow-sm">
                      <p className="text-sm font-medium">No dictations recorded yet today.</p>
                      <p className="text-xs mt-1">Press <span className="bg-gray-100 px-2 py-0.5 rounded font-mono text-slate-700">Ctrl+Shift</span> anywhere to start dictating!</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="bg-white rounded-2xl border border-[#E2E8F0] divide-y divide-[#E2E8F0] shadow-sm overflow-hidden">
                        {history.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage).map((item, idx) => (
                          <div key={idx} className="p-6 flex items-start space-x-6 hover:bg-gray-50 transition-colors group">
                            <div className="flex flex-col items-start min-w-[75px]">
                              <span className="text-xs font-medium text-[#64748B] whitespace-nowrap">{item.time_str || "Just now"}</span>
                              <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded mt-1 border border-blue-100">
                                {item.app_name || "Desktop"}
                              </span>
                            </div>
                            <div className="flex-1">
                              <p className="text-[#1E293B] leading-relaxed font-medium">{item.final_text || item.spoken_text}</p>
                            </div>
                            <div className="flex items-center space-x-3 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button 
                                onClick={() => copyToClipboard(item.final_text || item.spoken_text)}
                                className="p-1.5 text-[#64748B] hover:text-blue-600 hover:bg-white rounded-lg border border-transparent hover:border-[#E2E8F0] shadow-sm"
                                title="Copy to clipboard"
                              >
                                <Copy className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Clean 10-Item Batch Pagination Controls */}
                      {Math.ceil(history.length / itemsPerPage) > 1 && (
                        <div className="flex items-center justify-between px-2 pt-1 text-xs font-semibold text-[#64748B]">
                          <span>Showing page {currentPage} of {Math.ceil(history.length / itemsPerPage)} ({history.length} total)</span>
                          <div className="flex items-center space-x-2">
                            <button
                              disabled={currentPage === 1}
                              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                              className="px-3 py-1.5 bg-white border border-[#E2E8F0] rounded-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm"
                            >
                              Previous
                            </button>
                            <button
                              disabled={currentPage >= Math.ceil(history.length / itemsPerPage)}
                              onClick={() => setCurrentPage(prev => prev + 1)}
                              className="px-3 py-1.5 bg-white border border-[#E2E8F0] rounded-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm"
                            >
                              Next 10 →
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </section>
              </div>

              {/* Right Column: Stats Panel */}
              <aside className="w-full lg:w-72 space-y-6">
                <div className="bg-white rounded-2xl border border-[#E2E8F0] p-8 shadow-sm">
                  <div className="space-y-8">
                    <div className="text-center">
                      <p className="text-4xl font-serif italic text-[#1E293B]">{analytics.total_words || 0}</p>
                      <p className="text-xs font-bold text-[#64748B] uppercase tracking-widest mt-1">Total Words</p>
                    </div>
                    <div className="text-center">
                      <p className="text-4xl font-serif italic text-[#1E293B]">{Math.round(analytics.avg_wpm || 0)}</p>
                      <p className="text-xs font-bold text-[#64748B] uppercase tracking-widest mt-1">Average WPM</p>
                    </div>
                    <div className="text-center">
                      <p className="text-4xl font-serif italic text-[#1E293B]">{analytics.total_dictations > 0 ? 1 : 0}</p>
                      <p className="text-xs font-bold text-[#64748B] uppercase tracking-widest mt-1">Week Streak</p>
                    </div>
                  </div>

                  <hr className="my-8 border-[#E2E8F0]" />

                  <div>
                    <h4 className="text-sm font-bold text-[#1E293B] mb-1">Your Voice Profile</h4>
                    <p className="text-xs text-[#64748B] mb-4">Discover how you use your voice to command Velo AI.</p>
                    <div className="w-full bg-gray-100 h-1.5 rounded-full mb-2">
                      <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: '65%' }}></div>
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-bold text-[#64748B] uppercase">
                      <span>Optimizing</span>
                      <span>Unlocks in 2k words</span>
                    </div>
                  </div>
                </div>

                {/* Secondary Desktop Integration Card */}
                <div className="bg-blue-600 rounded-2xl p-6 text-white shadow-lg overflow-hidden relative">
                  <div className="relative z-10">
                    <p className="text-xs font-bold uppercase tracking-widest opacity-80 mb-2">Desktop Integration</p>
                    <h5 className="font-bold text-lg mb-4">Velo works anywhere you type.</h5>
                    <button className="bg-white/20 hover:bg-white/30 backdrop-blur-sm text-white border border-white/30 w-full py-2 rounded-xl text-sm font-bold transition-all">
                      Install Desktop Agent
                    </button>
                  </div>
                </div>
              </aside>
            </div>
          </div>
        )}

        {/* TAB 2: INSIGHTS VIEW (1:1 Wispr Flow Design Match) */}
        {activeTab === 'insights' && (
          <div className="max-w-5xl mx-auto space-y-8">
            {/* Header with Share Button */}
            <header className="flex justify-between items-start">
              <div>
                <h1 className="text-3xl font-bold text-[#1E293B]">Insights</h1>
              </div>
              <button className="flex items-center justify-center w-12 h-12 rounded-full border border-slate-200 bg-white text-slate-400 hover:text-slate-600 shadow-sm relative overflow-hidden group">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6a3 3 0 100-2.684m0 2.684l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
                <div className="absolute inset-0 border-2 border-dashed border-slate-200 rounded-full animate-[spin_10s_linear_infinite] group-hover:border-slate-400"></div>
              </button>
            </header>

            {/* Sub Nav Tabs */}
            <div className="flex border-b border-slate-200">
              <button className="px-1 py-3 text-sm font-semibold border-b-2 border-slate-900 mr-8 text-slate-900">Your usage</button>
              <button className="px-1 py-3 text-sm font-medium text-slate-400 hover:text-slate-600 transition-colors">Your voice</button>
            </div>

            {/* Top 3 Cards Grid (1:1 Wispr Flow Layout) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              
              {/* Card 1: WPM with Gauge */}
              <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm flex flex-col justify-between">
                <div>
                  <h2 className="text-6xl font-bold text-[#1E293B] mb-1">{Math.round(analytics.avg_wpm || 0)}</h2>
                  <div className="flex items-center gap-1 text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-6">
                    WORDS PER MINUTE
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"></path></svg>
                  </div>
                </div>

                {/* Semi-Circular Gauge */}
                <div className="flex flex-col items-center mt-2">
                  <div className="relative w-40 h-20 overflow-hidden">
                    <div className="w-40 h-40 rounded-full border-[18px] border-slate-100"></div>
                    <div className="absolute top-0 left-0 w-40 h-40 rounded-full border-[18px] border-transparent border-t-teal-600 border-r-teal-600 rotate-[45deg]"></div>
                    <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
                      <span className="text-[11px] text-slate-400">Top</span>
                      <span className="text-lg font-bold leading-tight text-slate-900">0.1%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Card 2: AI Fixes Breakdown */}
              <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm flex flex-col justify-between">
                <div>
                  <h2 className="text-6xl font-bold text-[#1E293B] mb-1">{analytics.total_fixes || 0}</h2>
                  <div className="text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-6">
                    FIXES MADE BY VELO AI
                  </div>
                </div>

                <div className="space-y-3 border-t border-slate-100 pt-4">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-600 font-medium">{analytics.total_fixes || 0} words corrected</span>
                    <svg className="w-3.5 h-3.5 text-slate-300" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"></path></svg>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-600 font-medium">0 dictionary fixes</span>
                    <svg className="w-3.5 h-3.5 text-slate-300" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"></path></svg>
                  </div>
                </div>
              </div>

              {/* Card 3: Total Words Dictated */}
              <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm flex flex-col justify-between">
                <div>
                  <h2 className="text-6xl font-bold text-[#1E293B] mb-1">{analytics.total_words || 0}</h2>
                  <div className="text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-6">
                    TOTAL WORDS DICTATED
                  </div>
                </div>

                <div className="space-y-3 border-t border-slate-100 pt-4">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-600 font-medium flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-teal-500"></span>
                      Desktop ({analytics.total_words || 0} words)
                    </span>
                  </div>
                  <div className="pt-1">
                    <span className="text-[11px] text-teal-700 bg-teal-50 px-2.5 py-1 rounded-full border border-teal-100 font-semibold inline-block">
                      100% Caret Accuracy
                    </span>
                  </div>
                </div>
              </div>

            </div>

            {/* SECTION 2: SUB-200MS PIPELINE LATENCY BREAKDOWN (New Component from Screenshot) */}
            <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm">
              <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🚀</span>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">SUB-200MS PIPELINE LATENCY BREAKDOWN</h3>
                </div>
                <div className="flex items-center gap-1.5 bg-emerald-50 text-emerald-700 px-3 py-1 rounded-full border border-emerald-100 text-xs font-bold">
                  <span>⚡</span>
                  <span>Sub-200ms Streak Active</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <div className="flex items-center gap-2 text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-2">
                    <Mic className="w-3.5 h-3.5 text-blue-500" />
                    STT LATENCY
                  </div>
                  <p className="text-2xl font-bold text-slate-900">{analytics.avg_stt_ms || 210.0} ms</p>
                </div>

                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <div className="flex items-center gap-2 text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-2">
                    <Sparkles className="w-3.5 h-3.5 text-purple-500" />
                    LLM LATENCY
                  </div>
                  <p className="text-2xl font-bold text-slate-900">{analytics.avg_llm_ms || 640.0} ms</p>
                </div>

                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <div className="flex items-center gap-2 text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-2">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    PASTE LATENCY
                  </div>
                  <p className="text-2xl font-bold text-slate-900">{analytics.avg_paste_ms || 2.5} ms</p>
                </div>

                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <div className="flex items-center gap-2 text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-2">
                    <Target className="w-3.5 h-3.5 text-emerald-500" />
                    TOTAL PIPELINE
                  </div>
                  <p className="text-2xl font-bold text-slate-900">{analytics.avg_total_ms || 852.5} ms</p>
                </div>
              </div>
            </div>

            {/* SECTION 3: DESKTOP USAGE & STREAK HEATMAP */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              {/* Desktop Usage Breakdown */}
              <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-slate-900 text-lg">Desktop usage</h3>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">TOTAL APPS USED | {Object.keys(analytics.app_breakdown || {}).length || 1}</span>
                </div>

                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs font-bold text-slate-700 mb-1.5">
                      <span className="flex items-center gap-2">⚡ {analytics.total_dictations || 1} DICTATIONS / PROMPTS</span>
                      <span>100%</span>
                    </div>
                    <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                      <div className="bg-teal-600 h-full rounded-full" style={{ width: '100%' }}></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-medium text-slate-400 mb-1.5">
                      <span>✉️ 0 EMAILS</span>
                      <span>0%</span>
                    </div>
                    <div className="w-full bg-slate-100 h-2.5 rounded-full"></div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-medium text-slate-400 mb-1.5">
                      <span>💬 0 WORK MESSAGES</span>
                      <span>0%</span>
                    </div>
                    <div className="w-full bg-slate-100 h-2.5 rounded-full"></div>
                  </div>
                </div>
              </div>

              {/* Day Streak Heatmap Grid */}
              <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-slate-900 text-lg">{analytics.total_dictations > 0 ? 1 : 0} day streak</h3>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">LONGEST STREAK | 1 DAY</span>
                </div>

                <div className="flex justify-between text-[10px] text-slate-400 font-bold uppercase mb-3 px-6">
                  <span>Mar</span><span>Apr</span><span>May</span><span>Jun</span><span>Jul</span>
                </div>

                {/* Heatmap Grid */}
                <div className="grid grid-cols-12 gap-1.5">
                  {Array.from({ length: 48 }).map((_, i) => (
                    <div 
                      key={i} 
                      className={`h-3 rounded-sm ${i === 47 ? 'bg-teal-600' : 'bg-slate-100'}`}
                    />
                  ))}
                </div>

                <div className="flex items-center gap-1.5 mt-6 text-[10px] text-slate-400 font-bold">
                  <span>Less</span>
                  <div className="w-2.5 h-2.5 rounded-sm bg-slate-100"></div>
                  <div className="w-2.5 h-2.5 rounded-sm bg-teal-200"></div>
                  <div className="w-2.5 h-2.5 rounded-sm bg-teal-400"></div>
                  <div className="w-2.5 h-2.5 rounded-sm bg-teal-600"></div>
                  <span>More</span>
                </div>
              </div>

            </div>
          </div>
        )}

        {/* TAB 3: DICTIONARY VIEW (1:1 Wispr Flow Design) */}
        {activeTab === 'dictionary' && (
          <div className="max-w-5xl mx-auto space-y-6">
            {/* Top Bar Header */}
            <header className="flex justify-between items-center">
              <h1 className="text-3xl font-bold text-[#1E293B]">Dictionary</h1>
              <button className="bg-slate-900 text-white font-bold px-4 py-2 rounded-xl text-sm hover:bg-slate-800 transition-colors shadow-sm inline-flex items-center gap-1.5">
                <span>+</span> Add new
              </button>
            </header>

            {/* Sub-nav Category Tabs */}
            <div className="flex border-b border-slate-200">
              <button className="px-1 py-3 text-sm font-semibold border-b-2 border-slate-900 mr-8 text-slate-900">All</button>
              <button className="px-1 py-3 text-sm font-medium text-slate-400 hover:text-slate-600 transition-colors mr-8">Personal</button>
              <button className="px-1 py-3 text-sm font-medium text-slate-400 hover:text-slate-600 transition-colors">Shared with team</button>
            </div>

            {/* Wispr Flow Warm Dark-Brown Custom Spells Banner */}
            <div className="relative rounded-2xl p-8 bg-[#2A2421] text-white shadow-xl overflow-hidden">
              <button className="absolute top-4 right-4 text-white/60 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>

              <div className="max-w-2xl space-y-3">
                <h2 className="text-2xl font-bold tracking-tight">Velo AI spells the way you do.</h2>
                <p className="text-xs text-amber-100/80 leading-relaxed">
                  Velo AI learns your unique words and names — automatically or manually. Add personal terms, company jargon, client names, or industry-specific lingo. Share them with your team so everyone stays on the same page.
                </p>
                
                <div className="flex flex-wrap gap-2.5 pt-3">
                  <button className="bg-white text-slate-900 font-bold px-3.5 py-1.5 rounded-lg text-xs shadow-md hover:bg-slate-100 transition-colors">
                    + Add new word
                  </button>
                  <span className="bg-[#3D3531] text-amber-100 px-3 py-1.5 rounded-lg text-xs font-medium border border-amber-900/40">VeloVoice</span>
                  <span className="bg-[#3D3531] text-amber-100 px-3 py-1.5 rounded-lg text-xs font-medium border border-amber-900/40">Rahul Bangle</span>
                  <span className="bg-[#3D3531] text-amber-100 px-3 py-1.5 rounded-lg text-xs font-medium border border-amber-900/40">Aakash</span>
                  <span className="bg-[#3D3531] text-amber-100 px-3 py-1.5 rounded-lg text-xs font-medium border border-amber-900/40">Groq Whisper</span>
                  <span className="bg-[#3D3531] text-amber-100 px-3 py-1.5 rounded-lg text-xs font-medium border border-amber-900/40">PyQT6</span>
                </div>
              </div>
            </div>

            {/* Dictionary Word List */}
            <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm divide-y divide-slate-100 overflow-hidden">
              {vocabulary.length === 0 ? (
                <div className="p-8 text-center text-slate-500 text-sm">
                  No learned dictionary terms in database yet. Correct words during dictation or add new words above!
                </div>
              ) : (
                vocabulary.map((item, idx) => (
                  <div key={idx} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors group">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800 text-sm">{item.term}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded font-bold border ${item.status.includes('Active') ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-amber-50 text-amber-700 border-amber-100'}`}>
                          {item.status}
                        </span>
                      </div>
                      {item.variants && item.variants.length > 0 && (
                        <p className="text-xs text-slate-400 mt-0.5">Phonetic sound keys: {item.variants.join(', ')}</p>
                      )}
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-bold text-slate-500 block">Used {item.usage_count}x</span>
                      <span className="text-[10px] text-slate-400">{item.category}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* TAB 4: SNIPPETS VIEW (1:1 Wispr Flow Design Match) */}
        {activeTab === 'snippets' && (
          <div className="max-w-5xl mx-auto space-y-6">
            {/* Header */}
            <header className="flex justify-between items-center">
              <h1 className="text-3xl font-bold text-[#1E293B]">Snippets</h1>
              <button 
                onClick={() => setSnippetModal({ isOpen: true, snippet: null })}
                className="bg-slate-900 text-white font-bold px-4 py-2 rounded-xl text-sm hover:bg-slate-800 transition-colors shadow-sm inline-flex items-center gap-1.5"
              >
                <span>+</span> Add new
              </button>
            </header>

            {/* Sub-nav Tabs & Tools */}
            <div className="flex justify-between items-center border-b border-slate-200">
              <div className="flex">
                <button className="px-1 py-3 text-sm font-semibold border-b-2 border-slate-900 mr-8 text-slate-900">All</button>
                <button className="px-1 py-3 text-sm font-medium text-slate-400 hover:text-slate-600 transition-colors mr-8">Personal</button>
                <button className="px-1 py-3 text-sm font-medium text-slate-400 hover:text-slate-600 transition-colors">Shared with team</button>
              </div>
              <div className="flex items-center space-x-3 text-slate-400 pb-2">
                <Search className="w-4 h-4 cursor-pointer hover:text-slate-600" />
              </div>
            </div>

            {/* Dark Styled Banner */}
            <div className="relative rounded-2xl p-8 bg-[#1F242D] text-white shadow-xl overflow-hidden">
              <button className="absolute top-4 right-4 text-white/60 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>

              <div className="max-w-2xl space-y-3">
                <h2 className="text-2xl font-bold tracking-tight">The stuff you shouldn't have to re-type</h2>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Save text you type often — an email, intro, or prompt — then say a word to drop it in instantly.
                </p>
                
                {/* Example Pills */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-3">
                  <div className="bg-white/10 backdrop-blur-md p-3 rounded-xl border border-white/10 text-xs">
                    <span className="font-bold text-blue-400 block mb-1">"my LinkedIn"</span>
                    <span className="text-slate-300 text-[11px] truncate block">https://linkedin.com/in/rahul-bangle</span>
                  </div>
                  <div className="bg-white/10 backdrop-blur-md p-3 rounded-xl border border-white/10 text-xs">
                    <span className="font-bold text-purple-400 block mb-1">"rewrite prompt"</span>
                    <span className="text-slate-300 text-[11px] truncate block">Rewrite this to be more concise...</span>
                  </div>
                  <div className="bg-white/10 backdrop-blur-md p-3 rounded-xl border border-white/10 text-xs">
                    <span className="font-bold text-emerald-400 block mb-1">"intro email"</span>
                    <span className="text-slate-300 text-[11px] truncate block">Hey, would love to find some time to chat...</span>
                  </div>
                </div>

                <div className="pt-2">
                  <button 
                    onClick={() => setSnippetModal({ isOpen: true, snippet: null })}
                    className="bg-white text-slate-900 font-bold px-4 py-2 rounded-xl text-xs shadow-md hover:bg-slate-100 transition-colors"
                  >
                    + Add new snippet
                  </button>
                </div>
              </div>
            </div>

            {/* Dynamic Snippets List Container */}
            <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm divide-y divide-slate-100 overflow-hidden">
              {snippets.map((snip) => (
                <div key={snip.id} className="p-5 flex items-center justify-between hover:bg-slate-50 transition-colors group">
                  <div>
                    <h4 className="font-bold text-slate-800 text-sm">{snip.title}</h4>
                    <p className="text-xs text-slate-500 mt-1">{snip.body}</p>
                  </div>
                  <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button 
                      onClick={() => setSnippetModal({ isOpen: true, snippet: snip })}
                      className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-white rounded-lg border border-transparent hover:border-slate-200 shadow-sm"
                      title="Edit snippet"
                    >
                      <FileEdit className="w-4 h-4" />
                    </button>
                    <button 
                      onClick={() => copyToClipboard(snip.body)}
                      className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-white rounded-lg border border-transparent hover:border-slate-200 shadow-sm"
                      title="Copy content"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

          </div>
        )}

      </main>

      {/* 3. EMBEDDED SETTINGS MODAL (1:1 Wispr Flow 2-Column Professional Design) */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 bg-[#1E293B]/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-[#E2E8F0] w-full max-w-3xl overflow-hidden flex h-[580px] animate-in fade-in zoom-in-95 duration-150">
            
            {/* Modal Left Sidebar */}
            <aside className="w-56 bg-slate-50 border-r border-[#E2E8F0] p-4 flex flex-col justify-between shrink-0">
              <div className="space-y-6">
                <div>
                  <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2">SETTINGS</h4>
                  <nav className="space-y-1">
                    <button 
                      onClick={() => setSettingsTab('general')}
                      className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${settingsTab === 'general' ? 'bg-white text-blue-600 shadow-sm border border-slate-200/60' : 'text-slate-600 hover:text-slate-900'}`}
                    >
                      <Settings className="w-4 h-4" />
                      <span>General</span>
                    </button>
                    <button 
                      onClick={() => setSettingsTab('system')}
                      className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${settingsTab === 'system' ? 'bg-white text-blue-600 shadow-sm border border-slate-200/60' : 'text-slate-600 hover:text-slate-900'}`}
                    >
                      <Zap className="w-4 h-4" />
                      <span>System & Engine</span>
                    </button>
                  </nav>
                </div>

                <div>
                  <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2">ACCOUNT</h4>
                  <nav className="space-y-1">
                    <button 
                      onClick={() => setSettingsTab('account')}
                      className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${settingsTab === 'account' ? 'bg-white text-blue-600 shadow-sm border border-slate-200/60' : 'text-slate-600 hover:text-slate-900'}`}
                    >
                      <User className="w-4 h-4" />
                      <span>Account & Billing</span>
                    </button>
                  </nav>
                </div>
              </div>

              <div className="px-3 pt-4 border-t border-slate-200/60 text-[11px] text-slate-400 font-medium">
                VeloVoice v1.0.0 Pro
              </div>
            </aside>

            {/* Modal Right Main Content */}
            <div className="flex-1 flex flex-col h-full overflow-hidden">
              <header className="px-8 py-5 border-b border-[#E2E8F0] flex justify-between items-center shrink-0">
                <h2 className="font-bold text-xl text-[#1E293B] capitalize">{settingsTab} Settings</h2>
                <button 
                  onClick={() => setIsSettingsOpen(false)}
                  className="p-1 text-[#64748B] hover:text-[#1E293B] rounded-lg hover:bg-slate-100 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </header>

              <div className="p-8 space-y-6 overflow-y-auto flex-1 text-sm text-slate-800">
                
                {/* TAB 1: GENERAL */}
                {settingsTab === 'general' && (
                  <div className="space-y-6">
                    {/* Hotkey Setting */}
                    <div className="flex items-center justify-between py-3 border-b border-slate-100">
                      <div>
                        <h4 className="font-bold text-slate-900 mb-0.5">Dictation Shortcut</h4>
                        <p className="text-xs text-slate-500">Hold key combination to dictate anywhere.</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="bg-slate-100 text-slate-800 font-mono text-xs px-3 py-1.5 rounded-lg border border-slate-200 font-bold">
                          {settingsState.hotkey}
                        </span>
                      </div>
                    </div>

                    {/* Microphone Device */}
                    <div className="flex items-center justify-between py-3 border-b border-slate-100">
                      <div>
                        <h4 className="font-bold text-slate-900 mb-0.5">Microphone Input</h4>
                        <p className="text-xs text-slate-500">Selected audio recording source device.</p>
                      </div>
                      <select 
                        value={settingsState.micDevice}
                        onChange={(e) => setSettingsState({ ...settingsState, micDevice: e.target.value })}
                        className="bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-800 px-3 py-1.5 rounded-xl focus:outline-none focus:border-blue-500"
                      >
                        <option>Default Microphone</option>
                        <option>Realtek High Definition Audio</option>
                        <option>Headset Microphone</option>
                      </select>
                    </div>

                    {/* Groq API Key */}
                    <div className="py-3 border-b border-slate-100 space-y-2">
                      <div className="flex justify-between items-center">
                        <h4 className="font-bold text-slate-900">Groq API Credentials</h4>
                        <span className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded font-bold border border-emerald-100">Verified</span>
                      </div>
                      <input 
                        type="password" 
                        value={settingsState.groqApiKey}
                        onChange={(e) => setSettingsState({ ...settingsState, groqApiKey: e.target.value })}
                        className="w-full bg-slate-50 border border-slate-200 font-mono text-xs px-3 py-2 rounded-xl focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  </div>
                )}

                {/* TAB 2: SYSTEM & ENGINE */}
                {settingsTab === 'system' && (
                  <div className="space-y-6">
                    {/* STT Model */}
                    <div className="flex items-center justify-between py-3 border-b border-slate-100">
                      <div>
                        <h4 className="font-bold text-slate-900 mb-0.5">Speech-to-Text Model</h4>
                        <p className="text-xs text-slate-500">Whisper engine for voice transcription.</p>
                      </div>
                      <select 
                        value={settingsState.sttModel}
                        onChange={(e) => setSettingsState({ ...settingsState, sttModel: e.target.value })}
                        className="bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-800 px-3 py-1.5 rounded-xl focus:outline-none focus:border-blue-500"
                      >
                        <option>whisper-large-v3-turbo (Groq Cloud)</option>
                        <option>faster-whisper small INT8 (Offline Fallback)</option>
                      </select>
                    </div>

                    {/* Auto-Paste Direct SendInput */}
                    <div className="flex items-center justify-between py-3 border-b border-slate-100">
                      <div>
                        <h4 className="font-bold text-slate-900 mb-0.5">Direct SendInput Injection</h4>
                        <p className="text-xs text-slate-500">Sub-10ms zero clipboard caret injection.</p>
                      </div>
                      <input 
                        type="checkbox"
                        checked={settingsState.directInjection}
                        onChange={(e) => setSettingsState({ ...settingsState, directInjection: e.target.checked })}
                        className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
                      />
                    </div>
                  </div>
                )}

                {/* TAB 3: ACCOUNT & BILLING */}
                {settingsTab === 'account' && (
                  <div className="space-y-6">
                    <div className="bg-purple-50 p-5 rounded-2xl border border-purple-100 flex justify-between items-center">
                      <div>
                        <h4 className="font-bold text-purple-900 text-base">VeloVoice Pro Plan</h4>
                        <p className="text-xs text-purple-700 mt-1">Active priority access to sub-second Whisper LPUs.</p>
                      </div>
                      <span className="bg-purple-600 text-white text-xs font-bold px-3 py-1.5 rounded-xl shadow-sm">
                        Active Pro
                      </span>
                    </div>

                    <div className="text-xs text-slate-500 space-y-1">
                      <p>Account Holder: <span className="font-bold text-slate-800">Rahul Bangle</span></p>
                      <p>Email: <span className="font-bold text-slate-800">bangleahul1@gmail.com</span></p>
                    </div>
                  </div>
                )}

              </div>

              <footer className="px-8 py-4 border-t border-[#E2E8F0] flex justify-end space-x-3 bg-slate-50 shrink-0">
                <button 
                  onClick={() => setIsSettingsOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-[#64748B] hover:text-[#1E293B] transition-colors"
                >
                  Cancel
                </button>
                <button 
                  onClick={handleSaveSettings}
                  className="px-5 py-2 text-xs font-bold bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors shadow-sm"
                >
                  Save Settings
                </button>
              </footer>
            </div>

          </div>
        </div>
      )}

      {/* 4. ADD / EDIT SNIPPET MODAL */}
      {snippetModal.isOpen && (
        <div className="fixed inset-0 z-50 bg-[#1E293B]/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-[#E2E8F0] w-full max-w-lg overflow-hidden flex flex-col">
            <header className="px-6 py-4 border-b border-[#E2E8F0] flex justify-between items-center bg-gray-50">
              <h2 className="font-bold text-lg text-[#1E293B]">
                {snippetModal.snippet ? "Edit Snippet" : "Add New Snippet"}
              </h2>
              <button 
                onClick={() => setSnippetModal({ isOpen: false, snippet: null })}
                className="p-1 text-[#64748B] hover:text-[#1E293B] rounded-lg hover:bg-gray-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </header>

            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
              const title = formData.get('title');
              const body = formData.get('body');
              
              if (snippetModal.snippet) {
                setSnippets(snippets.map(s => s.id === snippetModal.snippet.id ? { ...s, title, body } : s));
              } else {
                setSnippets([...snippets, { id: Date.now(), title, body }]);
              }
              setSnippetModal({ isOpen: false, snippet: null });
            }}>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-xs font-bold text-[#64748B] uppercase mb-1">Snippet Trigger Name</label>
                  <input 
                    name="title"
                    type="text" 
                    required
                    placeholder='e.g. "my email address"'
                    defaultValue={snippetModal.snippet?.title || ""} 
                    className="w-full border border-[#E2E8F0] rounded-xl px-4 py-2 text-sm font-semibold text-[#1E293B] focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-[#64748B] uppercase mb-1">Expanded Text Content</label>
                  <textarea 
                    name="body"
                    required
                    rows={4}
                    placeholder="Enter full text to inject..."
                    defaultValue={snippetModal.snippet?.body || ""} 
                    className="w-full border border-[#E2E8F0] rounded-xl px-4 py-2 text-sm text-[#1E293B] focus:outline-none focus:border-blue-500 font-mono"
                  />
                </div>
              </div>

              <footer className="px-6 py-4 border-t border-[#E2E8F0] flex justify-between items-center bg-gray-50">
                {snippetModal.snippet ? (
                  <button 
                    type="button"
                    onClick={() => {
                      setSnippets(snippets.filter(s => s.id !== snippetModal.snippet.id));
                      setSnippetModal({ isOpen: false, snippet: null });
                    }}
                    className="px-3 py-1.5 text-xs font-bold text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    Delete Snippet
                  </button>
                ) : <div />}

                <div className="flex space-x-2">
                  <button 
                    type="button"
                    onClick={() => setSnippetModal({ isOpen: false, snippet: null })}
                    className="px-4 py-2 text-sm font-semibold text-[#64748B] hover:text-[#1E293B] transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    className="px-5 py-2 text-sm font-bold bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors shadow-sm"
                  >
                    Save Snippet
                  </button>
                </div>
              </footer>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
