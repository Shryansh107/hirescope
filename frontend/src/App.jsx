import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Tag Input Component in React
const ReactTagInput = ({ label, tags, setTags, placeholder }) => {
  const [inputVal, setInputVal] = useState('');

  const addTag = (val) => {
    const trimmed = val.trim();
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed]);
    }
  };

  const removeTag = (index) => {
    setTags(tags.filter((_, idx) => idx !== index));
  };

  const handleKeyDown = (e) => {
    if ((e.key === 'Enter' || e.key === ',') && inputVal) {
      e.preventDefault();
      addTag(inputVal.replace(/,$/, ''));
      setInputVal('');
    }
  };

  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      <div className="tag-input-container">
        {tags.map((tag, idx) => (
          <span className="tag-pill" key={idx}>
            {tag}{' '}
            <button type="button" onClick={() => removeTag(idx)}>
              &times;
            </button>
          </span>
        ))}
        <input
          type="text"
          className="tag-input-field"
          placeholder={placeholder}
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (inputVal) {
              addTag(inputVal);
              setInputVal('');
            }
          }}
        />
      </div>
    </div>
  );
};

function App() {
  // --- State for Scraper Configurations ---
  const [keywords, setKeywords] = useState([]);
  const [jobTitles, setJobTitles] = useState([]);
  const [excludedKeywords, setExcludedKeywords] = useState([]);
  
  const [locations, setLocations] = useState([{ location: '', workplace: ['any'] }]);
  
  const [jobTypes, setJobTypes] = useState([]);
  const [experienceLevels, setExperienceLevels] = useState([]);
  
  const [yearsMin, setYearsMin] = useState('');
  const [yearsMax, setYearsMax] = useState('');
  const [payMin, setPayMin] = useState('');
  const [payMax, setPayMax] = useState('');
  const [currency, setCurrency] = useState('USD');
  
  const [requiredSkills, setRequiredSkills] = useState([]);
  const [companyNames, setCompanyNames] = useState([]);
  const [excludedCompanies, setExcludedCompanies] = useState([]);
  const [companySizes, setCompanySizes] = useState([]);
  const [industries, setIndustries] = useState([]);
  
  const [datePostedType, setDatePostedType] = useState('any');
  const [datePostedVal, setDatePostedVal] = useState('24');
  
  const [weightTitle, setWeightTitle] = useState(7);
  const [weightSkills, setWeightSkills] = useState(7);
  const [weightSalary, setWeightSalary] = useState(5);

  const [activeTab, setActiveTab] = useState('filters');
  const [profiles, setProfiles] = useState([]);
  const [activeProfileId, setActiveProfileId] = useState(null);

  // --- Scraper Live Status State ---
  const [isScraping, setIsScraping] = useState(false);
  const [scrapeRun, setScrapeRun] = useState(null);
  const [progressPct, setProgressPct] = useState(0);
  const [progressLabel, setProgressLabel] = useState('Starting…');
  const [progressLogs, setProgressLogs] = useState([]);
  const [showProgressModal, setShowProgressModal] = useState(false);
  
  // --- Sidebar Collapse ---
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // --- Jobs List & Table State ---
  const [allJobs, setAllJobs] = useState([]);
  const [filteredJobs, setFilteredJobs] = useState([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  
  // Table search & columns filters
  const [searchText, setSearchText] = useState('');
  const [filterWorkType, setFilterWorkType] = useState('');
  const [filterExperience, setFilterExperience] = useState('');
  const [filterDate, setFilterDate] = useState('');
  const [filterDays, setFilterDays] = useState('7');
  const [filterStatus, setFilterStatus] = useState('');
  
  // Sorting & Pagination
  const [sortCol, setSortCol] = useState('posted_at');
  const [sortDir, setSortDir] = useState('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  // --- Modal States ---
  const [selectedJob, setSelectedJob] = useState(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveProfileName, setSaveProfileName] = useState('');

  // --- Chatbot States ---
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [showKeyWarning, setShowKeyWarning] = useState(false);
  const [isBotTyping, setIsBotTyping] = useState(false);
  
  const chatMessagesEndRef = useRef(null);

  // --- Fetch Jobs on Mount ---
  const fetchJobs = async () => {
    setLoadingJobs(true);
    try {
      const res = await fetch('/api/jobs');
      if (res.ok) {
        const data = await res.ok ? await res.json() : [];
        setAllJobs(data);
      }
    } catch (e) {
      console.error("Failed to fetch jobs: ", e);
    }
    setLoadingJobs(false);
  };

  // --- Load Config Profiles ---
  const loadProfiles = async () => {
    try {
      const res = await fetch('/api/config/list');
      if (res.ok) {
        const data = await res.json();
        setProfiles(data);
        const active = data.find(c => c.is_active);
        if (active) {
          setActiveProfileId(active.id);
        }
      }
    } catch (e) {
      console.error("Failed to load profiles:", e);
    }
  };

  // Check Localhost
  const isLocal = window.location.hostname === 'localhost' || 
                  window.location.hostname === '127.0.0.1' || 
                  window.location.hostname.startsWith('192.168.') || 
                  window.location.hostname.startsWith('10.');

  useEffect(() => {
    fetchJobs();
    if (isLocal) {
      loadProfiles();
      // Load active config on startup
      (async () => {
        try {
          const res = await fetch('/api/config/list');
          if (res.ok) {
            const data = await res.json();
            const active = data.find(c => c.is_active);
            if (active) {
              writeConfigToForm(active);
            }
          }
        } catch (e) {}
      })();
    }
  }, []);

  // --- Apply Filters, Sorting, and Pagination ---
  useEffect(() => {
    let result = [...allJobs];

    // Quick Filter Search Text
    if (searchText) {
      const q = searchText.toLowerCase();
      result = result.filter(j => 
        (j.title || '').toLowerCase().includes(q) ||
        (j.company_name || '').toLowerCase().includes(q) ||
        (j.location || '').toLowerCase().includes(q)
      );
    }

    // Work Type dropdown
    if (filterWorkType) {
      result = result.filter(j => (j.formatted_work_type || '').toLowerCase().includes(filterWorkType.toLowerCase()));
    }

    // Experience dropdown
    if (filterExperience) {
      result = result.filter(j => (j.formatted_experience_level || '').toLowerCase().includes(filterExperience.toLowerCase()));
    }

    // Status dropdown
    if (filterStatus) {
      const statusNum = parseInt(filterStatus);
      result = result.filter(j => j.scraped === statusNum);
    }

    // Date Posted dropdown
    if (filterDate) {
      const now = new Date();
      if (filterDate === '24h') {
        const boundary = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        result = result.filter(j => j.posted_at && new Date(j.posted_at) >= boundary);
      } else if (filterDate === 'week') {
        const boundary = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        result = result.filter(j => j.posted_at && new Date(j.posted_at) >= boundary);
      } else if (filterDate === 'month') {
        const boundary = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        result = result.filter(j => j.posted_at && new Date(j.posted_at) >= boundary);
      } else if (filterDate === 'custom_days' && filterDays) {
        const days = parseInt(filterDays) || 7;
        const boundary = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
        result = result.filter(j => j.posted_at && new Date(j.posted_at) >= boundary);
      }
    }

    // Sorting
    result.sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol];
      if (va == null && vb != null) return 1;
      if (vb == null && va != null) return -1;
      if (va == null && vb == null) return 0;
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      return va < vb ? (sortDir === 'asc' ? -1 : 1) : va > vb ? (sortDir === 'asc' ? 1 : -1) : 0;
    });

    setFilteredJobs(result);
    setCurrentPage(1); // reset to page 1
  }, [allJobs, searchText, filterWorkType, filterExperience, filterDate, filterDays, filterStatus, sortCol, sortDir]);

  // --- Scraper Progress Poller ---
  const pollScraperStatus = async () => {
    try {
      const res = await fetch('/api/scrape/status');
      if (res.ok) {
        const run = await res.json();
        setScrapeRun(run);
        
        if (run && (run.status === 'running' || run.status === 'stopping')) {
          setIsScraping(true);
          
          // Calculate progress percentage
          let pct = 0;
          let label = 'Scraping…';
          if (run.total_pages > 0) {
            pct = Math.round((run.pages_scraped / run.total_pages) * 100);
          }
          if (run.status === 'stopping') {
            label = 'Stopping scraper…';
          } else {
            label = `Scraping page ${run.pages_scraped} of ${run.total_pages || '?'}`;
          }
          
          setProgressPct(pct);
          setProgressLabel(label);
          setProgressLogs(run.error_log || []);
        } else {
          // Idle or finished
          setIsScraping(false);
          setShowProgressModal(false);
          fetchJobs();
          loadProfiles();
        }
      }
    } catch (e) {
      console.error("Failed to poll scraper status:", e);
    }
  };

  // Poll intervals when scraping
  useEffect(() => {
    let timer = null;
    if (isScraping || showProgressModal) {
      timer = setInterval(pollScraperStatus, 2000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isScraping, showProgressModal]);

  // --- Dynamic Locations list logic ---
  const handleLocWorkplaceChange = (idx, value, checked) => {
    const nextLocs = [...locations];
    let currentWorkplace = nextLocs[idx].workplace || ['any'];

    if (value === 'any' && checked) {
      currentWorkplace = ['any'];
    } else if (checked) {
      currentWorkplace = currentWorkplace.filter(w => w !== 'any');
      if (!currentWorkplace.includes(value)) {
        currentWorkplace.push(value);
      }
    } else {
      currentWorkplace = currentWorkplace.filter(w => w !== value);
      if (currentWorkplace.length === 0) {
        currentWorkplace = ['any'];
      }
    }
    nextLocs[idx].workplace = currentWorkplace;
    setLocations(nextLocs);
  };

  const addLocationItem = (locName = '', workplaces = ['any']) => {
    setLocations([...locations, { location: locName, workplace: workplaces }]);
  };

  const removeLocationItem = (idx) => {
    setLocations(locations.filter((_, i) => i !== idx));
  };

  // --- Read Config from Form parameters ---
  const readConfigObj = () => {
    const locStr = JSON.stringify(locations.filter(l => l.location.trim()));
    return {
      keywords,
      job_titles: jobTitles,
      excluded_keywords: excludedKeywords,
      location: locStr,
      remote_filter: 'any',
      job_type: jobTypes,
      experience_level: experienceLevels,
      years_of_experience_min: parseInt(yearsMin) || null,
      years_of_experience_max: parseInt(yearsMax) || null,
      expected_pay_min: parseInt(payMin) || null,
      expected_pay_max: parseInt(payMax) || null,
      pay_currency: currency,
      required_skills: requiredSkills,
      preferred_skills: [],
      programming_languages: [],
      company_names: companyNames,
      excluded_companies: excludedCompanies,
      company_size: companySizes,
      industry: industries,
      date_posted: (function() {
        if (datePostedType === 'hours' || datePostedType === 'days') {
          return `${datePostedType}_${parseInt(datePostedVal) || 1}`;
        }
        return datePostedType;
      })(),
      max_jobs_to_scrape: 100,
      pages_to_scrape: 10,
      weight_title_match: weightTitle,
      weight_skills_match: weightSkills,
      weight_salary_match: weightSalary,
    };
  };

  // --- Write Config to Form parameters ---
  const writeConfigToForm = (cfg) => {
    setKeywords(cfg.keywords || []);
    setJobTitles(cfg.job_titles || []);
    setExcludedKeywords(cfg.excluded_keywords || []);
    
    let locationList = [];
    try {
      if (cfg.location && cfg.location.startsWith('[')) {
        locationList = JSON.parse(cfg.location);
      } else if (cfg.location) {
        locationList = [{ location: cfg.location, workplace: [cfg.remote_filter || 'any'] }];
      }
    } catch (e) {
      if (cfg.location) locationList = [{ location: cfg.location, workplace: [cfg.remote_filter || 'any'] }];
    }
    setLocations(locationList.length === 0 ? [{ location: '', workplace: ['any'] }] : locationList);
    
    setJobTypes(cfg.job_type || []);
    setExperienceLevels(cfg.experience_level || []);
    setYearsMin(cfg.years_of_experience_min || '');
    setYearsMax(cfg.years_of_experience_max || '');
    setPayMin(cfg.expected_pay_min || '');
    setPayMax(cfg.expected_pay_max || '');
    setCurrency(cfg.pay_currency || 'USD');
    
    const mergedSkills = [
      ...(cfg.required_skills || []),
      ...(cfg.preferred_skills || []),
      ...(cfg.programming_languages || [])
    ];
    setRequiredSkills(mergedSkills);
    setCompanyNames(cfg.company_names || []);
    setExcludedCompanies(cfg.excluded_companies || []);
    setCompanySizes(cfg.company_size || []);
    setIndustries(cfg.industry || []);
    
    const dateVal = cfg.date_posted || 'any';
    if (dateVal.startsWith('hours_')) {
      setDatePostedType('hours');
      setDatePostedVal(dateVal.split('_')[1]);
    } else if (dateVal.startsWith('days_')) {
      setDatePostedType('days');
      setDatePostedVal(dateVal.split('_')[1]);
    } else {
      setDatePostedType(dateVal);
    }
    
    setWeightTitle(cfg.weight_title_match ?? 7);
    setWeightSkills(cfg.weight_skills_match ?? 7);
    setWeightSalary(cfg.weight_salary_match ?? 5);
  };

  const resetConfig = () => {
    writeConfigToForm({
      keywords: [],
      job_titles: [],
      excluded_keywords: [],
      location: '',
      remote_filter: 'any',
      job_type: [],
      experience_level: [],
      required_skills: [],
      preferred_skills: [],
      programming_languages: [],
      company_names: [],
      excluded_companies: [],
      company_size: [],
      industry: [],
      date_posted: 'any',
      max_jobs_to_scrape: 100,
      pages_to_scrape: 10,
      weight_title_match: 7,
      weight_skills_match: 7,
      weight_salary_match: 5
    });
  };

  // --- CRUD Profiles API ---
  const saveProfile = async () => {
    if (!saveProfileName.trim()) return;
    const body = {
      ...readConfigObj(),
      profile_name: saveProfileName,
    };
    if (activeProfileId) {
      body.id = activeProfileId;
    }
    try {
      const res = await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (res.ok) {
        const saved = await res.json();
        setActiveProfileId(saved.id);
        // Activate it immediately
        await fetch(`/api/config/${saved.id}/activate`, { method: 'POST' });
        setShowSaveModal(false);
        setSaveProfileName('');
        loadProfiles();
      }
    } catch (e) {
      console.error("Failed to save profile:", e);
    }
  };

  const loadProfileById = async (id) => {
    try {
      const res = await fetch(`/api/config/${id}`);
      if (res.ok) {
        const cfg = await res.json();
        writeConfigToForm(cfg);
        setActiveProfileId(id);
        setActiveTab('filters');
      }
    } catch (e) {
      console.error("Failed to get profile:", e);
    }
  };

  const activateProfile = async (id) => {
    try {
      const res = await fetch(`/api/config/${id}/activate`, { method: 'POST' });
      if (res.ok) {
        setActiveProfileId(id);
        loadProfiles();
      }
    } catch (e) {
      console.error("Failed to activate profile:", e);
    }
  };

  const deleteProfile = async (id) => {
    try {
      const res = await fetch(`/api/config/${id}`, { method: 'DELETE' });
      if (res.ok) {
        if (activeProfileId === id) {
          setActiveProfileId(null);
        }
        loadProfiles();
      }
    } catch (e) {
      console.error("Failed to delete profile:", e);
    }
  };

  // --- Scraper Actions ---
  const startScraping = async () => {
    // Read the form state and save it as "Quick Scrape" first
    const activeCfg = readConfigObj();
    activeCfg.profile_name = 'Quick Scrape';
    
    try {
      const saveRes = await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(activeCfg)
      });
      if (saveRes.ok) {
        const saved = await saveRes.json();
        await fetch(`/api/config/${saved.id}/activate`, { method: 'POST' });
        
        // Start scraping
        const startRes = await fetch('/api/scrape/start', { method: 'POST' });
        if (startRes.ok) {
          setShowProgressModal(true);
          setProgressPct(0);
          setProgressLabel('Starting…');
          setProgressLogs([]);
          setIsScraping(true);
        }
      }
    } catch (e) {
      console.error("Failed to start scraping:", e);
    }
  };

  const stopScraping = async () => {
    try {
      await fetch('/api/scrape/stop', { method: 'POST' });
      setProgressLabel('Stopping scraper…');
    } catch (e) {
      console.error("Failed to stop scraper:", e);
    }
  };

  // --- Export / Import Profiles ---
  const exportProfile = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(readConfigObj()));
    const dlAnchorElem = document.createElement('a');
    dlAnchorElem.setAttribute("href", dataStr);
    dlAnchorElem.setAttribute("download", `job-scraper-profile.json`);
    dlAnchorElem.click();
  };

  const triggerImport = () => {
    document.getElementById('react-import-file-input').click();
  };

  const importProfile = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const cfg = JSON.parse(e.target.result);
        writeConfigToForm(cfg);
        setActiveProfileId(null);
      } catch (err) {
        alert("Invalid JSON profile format");
      }
    };
    reader.readAsText(file);
  };

  // --- Job Details modal launcher ---
  const openDetails = async (jobId) => {
    setSelectedJob({ title: 'Loading…', description: 'Please wait...' });
    setShowDetailsModal(true);
    try {
      const res = await fetch(`/api/job/${jobId}`);
      if (res.ok) {
        const d = await res.json();
        setSelectedJob(d);
      }
    } catch (e) {
      setSelectedJob({ title: 'Error', description: e.message });
    }
  };

  // --- Chatbot Controller Logic ---
  const toggleChatbot = () => {
    setIsChatOpen(!isChatOpen);
  };

  // Scroll to bottom of chat
  useEffect(() => {
    if (chatMessagesEndRef.current) {
      chatMessagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatHistory, isBotTyping]);

  const parseMarkdown = (text) => {
    if (!text) return "";
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    
    // Inline code
    html = html.replace(/`(.*?)`/g, "<code>$1</code>");
    
    // Split into paragraphs / lists
    const lines = html.split("\n");
    let result = [];
    let inList = false;
    let listItems = [];
    let keyIdx = 0;

    for (let line of lines) {
      line = line.trim();
      if (line.startsWith("* ") || line.startsWith("- ")) {
        if (!inList) {
          inList = true;
        }
        listItems.push(line.substring(2));
      } else {
        if (inList) {
          result.push(
            <ul key={keyIdx++}>
              {listItems.map((li, i) => (
                <li key={i} dangerouslySetInnerHTML={{ __html: li }} />
              ))}
            </ul>
          );
          listItems = [];
          inList = false;
        }
        if (line) {
          result.push(<p key={keyIdx++} dangerouslySetInnerHTML={{ __html: line }} />);
        }
      }
    }
    if (inList) {
      result.push(
        <ul key={keyIdx++}>
          {listItems.map((li, i) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: li }} />
          ))}
        </ul>
      );
    }
    return result;
  };

  const sendChatMessage = async () => {
    const text = chatInput.trim();
    if (!text) return;
    
    setChatInput('');
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    const userMsg = { role: 'user', content: text, time: timeStr };
    const nextHistory = [...chatHistory, userMsg];
    setChatHistory(nextHistory);
    setIsBotTyping(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: nextHistory.map(h => ({ role: h.role, content: h.content })) })
      });

      setIsBotTyping(false);

      if (res.ok) {
        const data = await res.json();
        if (data.error) {
          if (data.error.includes("GEMINI_API_KEY")) {
            setShowKeyWarning(true);
          } else {
            setChatHistory(prev => [
              ...prev,
              { role: 'assistant', content: `Error: ${data.error}`, time: timeStr, isError: true }
            ]);
          }
        } else {
          const reply = data.content || "No response content.";
          setChatHistory(prev => [
            ...prev,
            { role: 'assistant', content: reply, time: timeStr }
          ]);
        }
      } else {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
    } catch (e) {
      setIsBotTyping(false);
      setChatHistory(prev => [
        ...prev,
        { role: 'assistant', content: `Connection failed: ${e.message}`, time: timeStr, isError: true }
      ]);
    }
  };

  // --- Pagination Slice ---
  const totalPages = Math.ceil(filteredJobs.length / pageSize) || 1;
  const startIndex = (currentPage - 1) * pageSize;
  const pageJobs = filteredJobs.slice(startIndex, startIndex + pageSize);

  // --- Computed General Stats ---
  const totalJobsCount = allJobs.length;
  const scrapedJobsCount = allJobs.filter(j => j.scraped === 1).length;
  const remoteJobsCount = allJobs.filter(j => (j.formatted_work_type || '').toLowerCase().includes('remote')).length;
  const sponsoredJobsCount = allJobs.filter(j => j.sponsored).length;

  return (
    <div className="app-container">
      {/* ═══ Sidebar ═══ */}
      <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`} id="sidebar">
        <div className="sidebar-header">
          <h2>
            <i className="fa-solid fa-sliders" style={{ marginRight: '0.4rem', color: '#ffffff' }}></i>{' '}
            Scrape Config
          </h2>
          <button className="sidebar-toggle-inner" onClick={() => setIsSidebarCollapsed(true)}>
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>
        
        <div className="sidebar-tabs">
          <button
            className={`sidebar-tab ${activeTab === 'filters' ? 'active' : ''}`}
            onClick={() => setActiveTab('filters')}
          >
            Filters
          </button>
          <button
            className={`sidebar-tab ${activeTab === 'profiles' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('profiles');
              loadProfiles();
            }}
          >
            Saved Profiles
          </button>
        </div>

        <div className="sidebar-content">
          {activeTab === 'filters' && (
            <div className="tab-panel active">
              {/* Search Accordion */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Search <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <ReactTagInput
                    label="Keywords"
                    tags={keywords}
                    setTags={setKeywords}
                    placeholder="e.g. python, backend…"
                  />
                  <ReactTagInput
                    label="Target Job Titles"
                    tags={jobTitles}
                    setTags={setJobTitles}
                    placeholder="e.g. Software Engineer…"
                  />
                  <ReactTagInput
                    label="Excluded Keywords"
                    tags={excludedKeywords}
                    setTags={setExcludedKeywords}
                    placeholder="e.g. senior, lead…"
                  />
                </div>
              </div>

              {/* Location targets */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Locations & Work Types <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <div id="locations-list-container">
                    {locations.map((loc, idx) => (
                      <div className="location-item" key={idx}>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
                          <input
                            className="form-input loc-name-input"
                            placeholder="e.g. India, United States"
                            value={loc.location}
                            onChange={(e) => {
                              const nextLocs = [...locations];
                              nextLocs[idx].location = e.target.value;
                              setLocations(nextLocs);
                            }}
                            style={{ flex: 1, padding: '0.4rem 0.6rem', fontSize: '0.82rem' }}
                          />
                          <button
                            type="button"
                            className="btn-action"
                            onClick={() => removeLocationItem(idx)}
                            style={{ background: 'rgba(226, 39, 24, 0.1)', borderColor: 'rgba(226, 39, 24, 0.2)', color: '#f87171', width: '28px', height: '28px' }}
                          >
                            <i className="fa-solid fa-trash" style={{ fontSize: '0.75rem' }}></i>
                          </button>
                        </div>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label" style={{ fontSize: '0.75rem' }}>Workplace Types</label>
                          <div className="checkbox-group loc-workplaces" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                            {['any', 'on-site', 'remote', 'hybrid'].map(w => (
                              <label
                                className={`checkbox-item ${loc.workplace.includes(w) ? 'checked' : ''}`}
                                style={{ fontSize: '0.75rem', padding: '0.2rem 0.4rem' }}
                                key={w}
                              >
                                <input
                                  type="checkbox"
                                  value={w}
                                  checked={loc.workplace.includes(w)}
                                  onChange={(e) => handleLocWorkplaceChange(idx, w, e.target.checked)}
                                />{' '}
                                {w === 'on-site' ? 'On-site' : w.charAt(0).toUpperCase() + w.slice(1)}
                              </label>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => addLocationItem()}
                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', width: '100%', marginTop: '0.5rem' }}
                  >
                    <i className="fa-solid fa-plus"></i> Add Location Target
                  </button>
                </div>
              </div>

              {/* Job type */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Job Type <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <div className="checkbox-group">
                    {['full-time', 'part-time', 'contract', 'internship', 'temporary', 'volunteer'].map(type => {
                      const isChecked = jobTypes.includes(type);
                      return (
                        <label className={`checkbox-item ${isChecked ? 'checked' : ''}`} key={type}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              if (e.target.checked) setJobTypes([...jobTypes, type]);
                              else setJobTypes(jobTypes.filter(t => t !== type));
                            }}
                          />{' '}
                          {type.charAt(0).toUpperCase() + type.slice(1)}
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Experience */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Experience Level <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <div className="checkbox-group" style={{ marginBottom: '0.75rem' }}>
                    {['internship', 'entry', 'associate', 'mid-senior', 'director', 'executive'].map(exp => {
                      const isChecked = experienceLevels.includes(exp);
                      return (
                        <label className={`checkbox-item ${isChecked ? 'checked' : ''}`} key={exp}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              if (e.target.checked) setExperienceLevels([...experienceLevels, exp]);
                              else setExperienceLevels(experienceLevels.filter(x => x !== exp));
                            }}
                          />{' '}
                          {exp === 'entry' ? 'Entry level' : exp.charAt(0).toUpperCase() + exp.slice(1)}
                        </label>
                      );
                    })}
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Min Years</label>
                      <input
                        type="number"
                        className="form-input"
                        placeholder="0"
                        min="0"
                        value={yearsMin}
                        onChange={(e) => setYearsMin(e.target.value)}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Max Years</label>
                      <input
                        type="number"
                        className="form-input"
                        placeholder="Any"
                        min="0"
                        value={yearsMax}
                        onChange={(e) => setYearsMax(e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Compensation */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Compensation <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Min Pay</label>
                      <input
                        type="number"
                        className="form-input"
                        placeholder="e.g. 50000"
                        value={payMin}
                        onChange={(e) => setPayMin(e.target.value)}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Max Pay</label>
                      <input
                        type="number"
                        className="form-input"
                        placeholder="e.g. 150000"
                        value={payMax}
                        onChange={(e) => setPayMax(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Currency</label>
                    <select
                      className="form-input"
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                    >
                      <option value="USD">USD</option>
                      <option value="INR">INR</option>
                      <option value="EUR">EUR</option>
                      <option value="GBP">GBP</option>
                      <option value="CAD">CAD</option>
                      <option value="AUD">AUD</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Skills & Tech */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Skills & Tech <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <ReactTagInput
                    label="Target Skills & Technologies"
                    tags={requiredSkills}
                    setTags={setRequiredSkills}
                    placeholder="e.g. React, Node.js, Go, C++…"
                  />
                </div>
              </div>

              {/* Company */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Company <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <ReactTagInput
                    label="Target Companies"
                    tags={companyNames}
                    setTags={setCompanyNames}
                    placeholder="Whitelist…"
                  />
                  <ReactTagInput
                    label="Excluded Companies"
                    tags={excludedCompanies}
                    setTags={setExcludedCompanies}
                    placeholder="Blacklist…"
                  />
                  <div className="form-group">
                    <label className="form-label">Company Size</label>
                    <div className="checkbox-group">
                      {['1-10', '11-50', '51-200', '201-500', '501-1000', '1001-5000', '5001-10000', '10001+'].map(sz => {
                        const isChecked = companySizes.includes(sz);
                        return (
                          <label className={`checkbox-item ${isChecked ? 'checked' : ''}`} key={sz}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => {
                                if (e.target.checked) setCompanySizes([...companySizes, sz]);
                                else setCompanySizes(companySizes.filter(s => s !== sz));
                              }}
                            />{' '}
                            {sz}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                  <ReactTagInput
                    label="Industry"
                    tags={industries}
                    setTags={setIndustries}
                    placeholder="e.g. Software, Fintech…"
                  />
                </div>
              </div>

              {/* Date Posted */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Date Posted <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <div className="form-group">
                    <label className="form-label">Post Window</label>
                    <select
                      className="form-input"
                      value={datePostedType}
                      onChange={(e) => setDatePostedType(e.target.value)}
                      style={{ marginBottom: '0.5rem', width: '100%' }}
                    >
                      <option value="any">Any time</option>
                      <option value="hours">Past X Hours</option>
                      <option value="days">Past X Days</option>
                      <option value="past_week">Past Week</option>
                      <option value="past_month">Past Month</option>
                    </select>
                  </div>
                  {(datePostedType === 'hours' || datePostedType === 'days') && (
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">
                        Number of {datePostedType === 'hours' ? 'Hours' : 'Days'}
                      </label>
                      <input
                        type="number"
                        className="form-input"
                        min="1"
                        value={datePostedVal}
                        onChange={(e) => setDatePostedVal(e.target.value)}
                        style={{ width: '100%' }}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Weights */}
              <div className="accordion-section open">
                <div className="accordion-header">
                  Relevance Weights <i className="fa-solid fa-chevron-down"></i>
                </div>
                <div className="accordion-body">
                  <div className="form-group">
                    <label className="form-label">Title Match</label>
                    <div className="range-row">
                      <input
                        type="range"
                        min="0"
                        max="10"
                        value={weightTitle}
                        onChange={(e) => setWeightTitle(parseInt(e.target.value))}
                      />
                      <span className="range-value">{weightTitle}</span>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Skills Match</label>
                    <div className="range-row">
                      <input
                        type="range"
                        min="0"
                        max="10"
                        value={weightSkills}
                        onChange={(e) => setWeightSkills(parseInt(e.target.value))}
                      />
                      <span className="range-value">{weightSkills}</span>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Salary Match</label>
                    <div className="range-row">
                      <input
                        type="range"
                        min="0"
                        max="10"
                        value={weightSalary}
                        onChange={(e) => setWeightSalary(parseInt(e.target.value))}
                      />
                      <span className="range-value">{weightSalary}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'profiles' && (
            <div className="tab-panel active">
              <div className="profile-list">
                {profiles.length === 0 ? (
                  <div className="empty-state" style={{ padding: '2rem 1rem' }}>
                    <i className="fa-solid fa-bookmark"></i>
                    <p style={{ fontSize: '0.85rem' }}>No saved profiles yet</p>
                  </div>
                ) : (
                  profiles.map(p => (
                    <div
                      className={`profile-card ${activeProfileId === p.id ? 'active-profile' : ''}`}
                      key={p.id}
                    >
                      <div className="profile-card-header">
                        <span className="profile-card-name">{p.profile_name}</span>
                        {p.is_active ? <span className="profile-card-badge">Active</span> : null}
                      </div>
                      <div className="profile-card-date">
                        Updated: {new Date(p.updated_at).toLocaleDateString()}
                      </div>
                      <div className="profile-card-actions">
                        <button className="btn btn-outline" onClick={() => loadProfileById(p.id)}>
                          Load
                        </button>
                        {!p.is_active && (
                          <button className="btn btn-outline" onClick={() => activateProfile(p.id)}>
                            Activate
                          </button>
                        )}
                        {p.profile_name !== 'Default Tech (0-2 years)' && (
                          <button className="btn btn-danger-outline" onClick={() => deleteProfile(p.id)}>
                            Delete
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar Actions */}
        {activeTab === 'filters' && (
          <div className="sidebar-actions">
            <div className="btn-row">
              <button className="btn btn-outline" onClick={() => setShowSaveModal(true)}>
                <i className="fa-solid fa-floppy-disk"></i> Save
              </button>
              <button className="btn btn-outline" onClick={resetConfig}>
                <i className="fa-solid fa-rotate-left"></i> Reset
              </button>
            </div>
            <div className="btn-row">
              <button className="btn btn-outline" onClick={exportProfile}>
                <i className="fa-solid fa-file-export"></i> Export
              </button>
              <button className="btn btn-outline" onClick={triggerImport}>
                <i className="fa-solid fa-file-import"></i> Import
              </button>
              <input
                type="file"
                id="react-import-file-input"
                style={{ display: 'none' }}
                accept=".json"
                onChange={importProfile}
              />
            </div>
            <button
              className="btn btn-primary"
              id="btn-start-scrape"
              onClick={startScraping}
              disabled={isScraping}
            >
              <i className="fa-solid fa-rocket"></i> Start Scraping
            </button>
          </div>
        )}
      </aside>

      {/* ═══ Main Content ═══ */}
      <div className="main-content">
        <div className="container">
          <header>
            <div className="header-left">
              {isSidebarCollapsed && (
                <button
                  className="sidebar-toggle"
                  onClick={() => setIsSidebarCollapsed(false)}
                  title="Toggle scrape config"
                >
                  <i className="fa-solid fa-bars"></i>
                </button>
              )}
              <div className="logo-area">
                <i className="fa-solid fa-database logo-icon"></i>
                <div className="logo-text">
                  <h1>LINKEDIN JOB SCRAPER</h1>
                  <p>High-Performance Job Scrape Console</p>
                </div>
              </div>
            </div>
            <div className="stats-badge" id="live-indicator">
              {isScraping ? (
                <>
                  <span className="spinner" style={{ width: '12px', height: '12px', borderWidth: '2px' }}></span>
                  <span style={{ color: '#ef4444' }}>● LIVE SCRAPING</span>
                </>
              ) : (
                <>
                  <span style={{ display: 'inline-block', width: '8px', height: '8px', background: '#22c55e', borderRadius: '50%' }}></span>
                  <span>SYSTEM READY</span>
                </>
              )}
            </div>
          </header>

          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon">
                <i className="fa-solid fa-briefcase"></i>
              </div>
              <div className="stat-info">
                <h3>Total Jobs</h3>
                <div className="stat-number">{totalJobsCount}</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">
                <i className="fa-solid fa-circle-check"></i>
              </div>
              <div className="stat-info">
                <h3>Fully Scraped</h3>
                <div className="stat-number">{scrapedJobsCount}</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">
                <i className="fa-solid fa-globe"></i>
              </div>
              <div className="stat-info">
                <h3>Remote</h3>
                <div className="stat-number">{remoteJobsCount}</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">
                <i className="fa-solid fa-bolt"></i>
              </div>
              <div className="stat-info">
                <h3>Sponsored</h3>
                <div className="stat-number">{sponsoredJobsCount}</div>
              </div>
            </div>
          </div>

          {/* Quick Filter Bar */}
          <div className="filter-bar">
            <div className="input-group">
              <label htmlFor="search-input">Search</label>
              <input
                type="text"
                id="search-input"
                className="input-control"
                placeholder="Title, company, location…"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
              />
            </div>
            <div className="input-group" style={{ maxWidth: '170px' }}>
              <label htmlFor="filter-worktype">Work Type</label>
              <select
                id="filter-worktype"
                className="input-control"
                value={filterWorkType}
                onChange={(e) => setFilterWorkType(e.target.value)}
              >
                <option value="">All</option>
                <option value="Full-time">Full-time</option>
                <option value="Part-time">Part-time</option>
                <option value="Contract">Contract</option>
                <option value="Internship">Internship</option>
              </select>
            </div>
            <div className="input-group" style={{ maxWidth: '170px' }}>
              <label htmlFor="filter-experience">Experience</label>
              <select
                id="filter-experience"
                className="input-control"
                value={filterExperience}
                onChange={(e) => setFilterExperience(e.target.value)}
              >
                <option value="">All</option>
                <option value="Internship">Internship</option>
                <option value="Entry level">Entry level</option>
                <option value="Associate">Associate</option>
                <option value="Mid-Senior level">Mid-Senior level</option>
              </select>
            </div>
            <div className="input-group" style={{ maxWidth: '170px' }}>
              <label htmlFor="filter-date">Date Posted</label>
              <select
                id="filter-date"
                className="input-control"
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
              >
                <option value="">All</option>
                <option value="24h">Past 24 Hours</option>
                <option value="week">Past Week</option>
                <option value="month">Past Month</option>
                <option value="custom_days">Past Days</option>
              </select>
            </div>
            {filterDate === 'custom_days' && (
              <div className="input-group" style={{ maxWidth: '120px' }}>
                <label htmlFor="filter-days">Days</label>
                <input
                  type="number"
                  min="1"
                  step="1"
                  id="filter-days"
                  className="input-control"
                  value={filterDays}
                  onChange={(e) => setFilterDays(e.target.value)}
                />
              </div>
            )}
            <div className="input-group" style={{ maxWidth: '150px' }}>
              <label htmlFor="filter-scraped">Status</label>
              <select
                id="filter-scraped"
                className="input-control"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="">All</option>
                <option value="1">Scraped</option>
                <option value="0">Pending</option>
              </select>
            </div>
          </div>

          {/* Table Section */}
          <div className="table-section">
            <div className="table-header-bar">
              <h2 id="jobs-count-text">Jobs ({filteredJobs.length.toLocaleString()})</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <button
                  className="btn btn-outline"
                  onClick={() => {
                    setSortCol('posted_at');
                    setSortDir('desc');
                  }}
                  style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem' }}
                >
                  <i className="fa-solid fa-clock"></i> Most Recent
                </button>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  Showing {filteredJobs.length > 0 ? `${startIndex + 1}-${Math.min(startIndex + pageSize, filteredJobs.length)}` : '0'} of {filteredJobs.length}
                </div>
              </div>
            </div>
            
            <div className="table-wrapper">
              {loadingJobs ? (
                <div className="loading-overlay">
                  <div className="spinner"></div>
                  <p>Loading jobs…</p>
                </div>
              ) : filteredJobs.length === 0 ? (
                <div className="empty-state">
                  <i className="fa-solid fa-magnifying-glass"></i>
                  <h3>No Jobs Found</h3>
                  <p>Try adjusting your search or scraper filters.</p>
                </div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th
                        className="sortable"
                        onClick={() => {
                          setSortDir(sortCol === 'title' && sortDir === 'asc' ? 'desc' : 'asc');
                          setSortCol('title');
                        }}
                      >
                        Title{' '}
                        <i
                          className={`fa-solid ${
                            sortCol === 'title'
                              ? sortDir === 'asc'
                                ? 'fa-sort-up'
                                : 'fa-sort-down'
                              : 'fa-sort'
                          }`}
                        ></i>
                      </th>
                      <th
                        className="sortable"
                        onClick={() => {
                          setSortDir(sortCol === 'company_name' && sortDir === 'asc' ? 'desc' : 'asc');
                          setSortCol('company_name');
                        }}
                      >
                        Company{' '}
                        <i
                          className={`fa-solid ${
                            sortCol === 'company_name'
                              ? sortDir === 'asc'
                                ? 'fa-sort-up'
                                : 'fa-sort-down'
                              : 'fa-sort'
                          }`}
                        ></i>
                      </th>
                      <th
                        className="sortable"
                        onClick={() => {
                          setSortDir(sortCol === 'location' && sortDir === 'asc' ? 'desc' : 'asc');
                          setSortCol('location');
                        }}
                      >
                        Location{' '}
                        <i
                          className={`fa-solid ${
                            sortCol === 'location'
                              ? sortDir === 'asc'
                                ? 'fa-sort-up'
                                : 'fa-sort-down'
                              : 'fa-sort'
                          }`}
                        ></i>
                      </th>
                      <th>Type</th>
                      <th
                        className="sortable"
                        onClick={() => {
                          setSortDir(sortCol === 'years_experience' && sortDir === 'asc' ? 'desc' : 'asc');
                          setSortCol('years_experience');
                        }}
                      >
                        Exp{' '}
                        <i
                          className={`fa-solid ${
                            sortCol === 'years_experience'
                              ? sortDir === 'asc'
                                ? 'fa-sort-up'
                                : 'fa-sort-down'
                              : 'fa-sort'
                          }`}
                        ></i>
                      </th>
                      <th>Salary</th>
                      <th
                        className="sortable"
                        onClick={() => {
                          setSortDir(sortCol === 'relevance_score' && sortDir === 'asc' ? 'desc' : 'asc');
                          setSortCol('relevance_score');
                        }}
                      >
                        Relevance{' '}
                        <i
                          className={`fa-solid ${
                            sortCol === 'relevance_score'
                              ? sortDir === 'asc'
                                ? 'fa-sort-up'
                                : 'fa-sort-down'
                              : 'fa-sort'
                          }`}
                        ></i>
                      </th>
                      <th
                        className="sortable"
                        onClick={() => {
                          setSortDir(sortCol === 'scraped' && sortDir === 'asc' ? 'desc' : 'asc');
                          setSortCol('scraped');
                        }}
                      >
                        Status{' '}
                        <i
                          className={`fa-solid ${
                            sortCol === 'scraped'
                              ? sortDir === 'asc'
                                ? 'fa-sort-up'
                                : 'fa-sort-down'
                              : 'fa-sort'
                          }`}
                        ></i>
                      </th>
                      <th style={{ width: '80px' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageJobs.map(j => {
                      let salaryText = '';
                      if (j.min_salary || j.max_salary) {
                        const mn = j.min_salary ? Math.round(j.min_salary).toLocaleString() : '';
                        const mx = j.max_salary ? Math.round(j.max_salary).toLocaleString() : '';
                        salaryText = `${j.currency || 'USD'} ${mn}${mn && mx ? ' - ' : ''}${mx}`;
                      }

                      let relevanceClass = 'relevance-none';
                      if (j.relevance_score != null) {
                        relevanceClass = j.relevance_score >= 70 ? 'relevance-high' : j.relevance_score >= 40 ? 'relevance-mid' : 'relevance-low';
                      }

                      return (
                        <tr key={j.job_id}>
                          <td className="job-title-col" title={j.title || ''}>{j.title}</td>
                          <td className="company-col">{j.company_name}</td>
                          <td>{j.location}</td>
                          <td>
                            {j.formatted_work_type && (
                              <span className="worktype-badge">{j.formatted_work_type}</span>
                            )}
                          </td>
                          <td style={{ fontSize: '0.8rem' }}>{j.formatted_experience_level}</td>
                          <td>
                            {salaryText && <span className="salary-badge">{salaryText}</span>}
                          </td>
                          <td>
                            <span className={`relevance-badge ${relevanceClass}`}>
                              {j.relevance_score != null ? j.relevance_score : '—'}
                            </span>
                          </td>
                          <td>
                            {j.scraped > 0 ? (
                              <span className="status-badge scraped">
                                <i className="fa-solid fa-circle-check"></i> Scraped
                              </span>
                            ) : (
                              <span className="status-badge pending">
                                <i className="fa-solid fa-clock"></i> Pending
                              </span>
                            )}
                          </td>
                          <td>
                            <div className="action-cell">
                              <button
                                className="btn-action"
                                title="Details"
                                onClick={() => openDetails(j.job_id)}
                              >
                                <i className="fa-solid fa-circle-info"></i>
                              </button>
                              {j.job_posting_url && (
                                <a
                                  href={j.job_posting_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="btn-action"
                                  title="LinkedIn"
                                >
                                  <i className="fa-brands fa-linkedin-in"></i>
                                </a>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            <div className="pagination-bar">
              <div className="pagination-info">
                Page {currentPage} of {totalPages}
              </div>
              <div className="pagination-controls">
                <button
                  className="btn-nav-page"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                >
                  <i className="fa-solid fa-angle-left"></i>
                </button>
                <span>{currentPage}</span>
                <button
                  className="btn-nav-page"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                >
                  <i className="fa-solid fa-angle-right"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ Job Details Modal ═══ */}
      {showDetailsModal && selectedJob && (
        <div className="modal-overlay active">
          <div className="modal-container">
            <div className="modal-header">
              <div>
                <div style={{ fontSize: '0.82rem', color: '#ffffff', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>
                  {selectedJob.company_name}
                </div>
                <h3>{selectedJob.title}</h3>
              </div>
              <button className="modal-close" onClick={() => setShowDetailsModal(false)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            
            <div className="modal-content">
              <div className="modal-meta-grid">
                <div className="meta-item">
                  <i className="fa-solid fa-map-pin"></i>
                  <div>
                    <div className="meta-value-label">Location</div>
                    <div className="meta-value">{selectedJob.location || 'N/A'}</div>
                  </div>
                </div>
                <div className="meta-item">
                  <i className="fa-solid fa-briefcase"></i>
                  <div>
                    <div className="meta-value-label">Type</div>
                    <div className="meta-value">{selectedJob.formatted_work_type || 'N/A'}</div>
                  </div>
                </div>
                <div className="meta-item">
                  <i className="fa-solid fa-layer-group"></i>
                  <div>
                    <div className="meta-value-label">Experience</div>
                    <div className="meta-value">{selectedJob.formatted_experience_level || 'N/A'}</div>
                  </div>
                </div>
                <div className="meta-item">
                  <i className="fa-solid fa-dollar-sign"></i>
                  <div>
                    <div className="meta-value-label">Salary</div>
                    <div className="meta-value">
                      {selectedJob.min_salary || selectedJob.max_salary ? (
                        `${selectedJob.currency || 'USD'} ${Math.round(selectedJob.min_salary || 0).toLocaleString()} - ${Math.round(selectedJob.max_salary || 0).toLocaleString()}`
                      ) : (
                        'Not listed'
                      )}
                    </div>
                  </div>
                </div>
                <div className="meta-item">
                  <i className="fa-solid fa-star"></i>
                  <div>
                    <div className="meta-value-label">Relevance</div>
                    <div className="meta-value">{selectedJob.relevance_score != null ? `${selectedJob.relevance_score}/100` : 'N/A'}</div>
                  </div>
                </div>
                <div className="meta-item">
                  <i className="fa-regular fa-calendar"></i>
                  <div>
                    <div className="meta-value-label">Posted</div>
                    <div className="meta-value">
                      {selectedJob.posted_at ? new Date(selectedJob.posted_at).toLocaleDateString() : 'N/A'}
                    </div>
                  </div>
                </div>
              </div>
              
              <div>
                <h3 className="modal-section-title">Description</h3>
                <div className="job-description-content">{selectedJob.description || 'No description available.'}</div>
              </div>
              
              {selectedJob.skills_desc && (
                <div>
                  <h3 className="modal-section-title">Skills</h3>
                  <div className="job-description-content">{selectedJob.skills_desc}</div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              {selectedJob.job_posting_url && (
                <a
                  href={selectedJob.job_posting_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-outline"
                >
                  <i className="fa-brands fa-linkedin"></i> LinkedIn
                </a>
              )}
              {selectedJob.application_url && (
                <a
                  href={selectedJob.application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary"
                >
                  Apply <i className="fa-solid fa-arrow-up-right-from-square"></i>
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ Progress Modal ═══ */}
      {showProgressModal && (
        <div className="modal-overlay progress-modal active">
          <div className="modal-container">
            <div className="modal-header">
              <h3>Scraping in Progress</h3>
              <button className="modal-close" onClick={() => setShowProgressModal(false)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            
            <div className="modal-content">
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{progressLabel}</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#ffffff' }}>
                    {progressPct}%
                  </span>
                </div>
                <div className="progress-bar-track">
                  <div className="progress-bar-fill" style={{ width: `${progressPct}%` }}></div>
                </div>
              </div>
              
              <div className="progress-stats">
                <div className="progress-stat">
                  <div className="progress-stat-value">{scrapeRun?.pages_scraped || 0}</div>
                  <div className="progress-stat-label">Pages</div>
                </div>
                <div className="progress-stat">
                  <div className="progress-stat-value">{scrapeRun?.total_found || 0}</div>
                  <div className="progress-stat-label">Found</div>
                </div>
                <div className="progress-stat">
                  <div className="progress-stat-value">{scrapeRun?.new_jobs || 0}</div>
                  <div className="progress-stat-label">New</div>
                </div>
                <div className="progress-stat">
                  <div className="progress-stat-value" style={{ color: scrapeRun?.errors > 0 ? '#e22718' : '#ffffff' }}>
                    {scrapeRun?.errors || 0}
                  </div>
                  <div className="progress-stat-label">Errors</div>
                </div>
              </div>
              
              <div>
                <h3 className="modal-section-title">Console Output</h3>
                <div className="progress-log">
                  {progressLogs.length === 0 ? (
                    <div style={{ color: '#7e7e7e' }}>Waiting for logs…</div>
                  ) : (
                    progressLogs.map((log, idx) => <div key={idx}>{log}</div>)
                  )}
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-danger-outline" onClick={stopScraping}>
                Stop Scraper
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Save Profile Modal ═══ */}
      {showSaveModal && (
        <div className="modal-overlay save-modal active">
          <div className="modal-container">
            <div className="modal-header">
              <h3>Save Profile</h3>
              <button className="modal-close" onClick={() => setShowSaveModal(false)}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>
            
            <div className="modal-content">
              <div className="form-group">
                <label className="form-label">Profile Name</label>
                <input
                  className="form-input"
                  placeholder="e.g. Backend India Remote"
                  value={saveProfileName}
                  onChange={(e) => setSaveProfileName(e.target.value)}
                />
              </div>
            </div>
            
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setShowSaveModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" style={{ width: 'auto' }} onClick={saveProfile}>
                <i className="fa-solid fa-check"></i> Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ BMW M Chatbot Elements ═══ */}
      <button className="chatbot-launcher-btn" onClick={toggleChatbot} title="Toggle Job Chatbot">
        <i className="fa-solid fa-comments"></i>
      </button>

      <div className={`chatbot-panel ${isChatOpen ? 'active' : ''}`} id="chatbot-panel">
        <div className="chatbot-m-stripe"></div>
        <div className="chatbot-header">
          <h3>BMW M JOB CHATBOT</h3>
          <button className="chatbot-close-btn" onClick={toggleChatbot}>
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>
        
        <div className="chatbot-messages">
          <div className="chat-msg assistant">
            <div className="chat-bubble">
              <p>Welcome to the M high-performance Job Scraper Console. How can I assist you with your jobs database today?</p>
            </div>
            <div className="chat-msg-time">CONSOLE · JUST NOW</div>
          </div>

          {chatHistory.map((msg, idx) => (
            <div className={`chat-msg ${msg.role === 'user' ? 'user' : 'assistant'}`} key={idx}>
              <div className="chat-bubble" style={msg.isError ? { borderColor: '#e22718', color: '#e22718' } : {}}>
                {msg.role === 'user' ? <p>{msg.content}</p> : parseMarkdown(msg.content)}
              </div>
              <div className="chat-msg-time">{msg.role === 'user' ? 'USER' : 'CONSOLE'} · {msg.time}</div>
            </div>
          ))}

          {isBotTyping && (
            <div className="chat-msg assistant">
              <div className="chat-bubble" style={{ padding: '0.5rem 1rem' }}>
                <div className="chat-typing-indicator">
                  <div className="chat-typing-dot"></div>
                  <div className="chat-typing-dot"></div>
                  <div className="chat-typing-dot"></div>
                </div>
              </div>
            </div>
          )}
          <div ref={chatMessagesEndRef} />
        </div>

        <div className="chatbot-input-container">
          <input
            type="text"
            className="chatbot-input"
            placeholder="Ask about jobs, salaries, locations..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') sendChatMessage();
            }}
          />
          <button className="chatbot-send-btn" onClick={sendChatMessage}>
            Send
          </button>
        </div>

        {/* Warning Overlay */}
        {showKeyWarning && (
          <div className="chatbot-warning-overlay">
            <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: '2rem', color: '#e22718', marginBottom: '1rem' }}></i>
            <h4>GEMINI API KEY REQUIRED</h4>
            <p>To enable the Job Chatbot, please add your Google Gemini API Key to the .env file in the project root.</p>
            <div className="chatbot-warning-code">GEMINI_API_KEY=your_key_here</div>
            <button className="btn btn-outline" style={{ width: '100%' }} onClick={() => setShowKeyWarning(false)}>
              Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
