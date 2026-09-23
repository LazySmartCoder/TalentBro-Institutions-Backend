"""Curated research notes on companies that commonly run placement drives.

Used by the mock interview to set the room the candidate is walked into: the
company's actual environment, how it likes to hire, and the flavour of
questions its panels ask. When a company is not in the knowledge base the
caller falls back to a generic framework instead of answering nothing.

This is static research (reviewed periodically), not a live web lookup, so the
interview stays fast and offline-friendly.
"""

import re

COMPANY_INSIGHTS = {
    'tcs': {
        'keywords': ['tcs', 'tata consultanc', 'tata consultancy'],
        'about': (
            'TCS is one of the world\'s largest IT services companies (Tata group) with over '
            '600,000 employees, delivering application development, cloud, AI and consulting '
            'for enterprise clients across banking, retail, healthcare and more.'
        ),
        'environment': (
            'A warm but process-driven Tata culture: disciplined, hierarchical in a polite way, '
            'client-focused, and huge on training. Fresher hiring goes through bands (Ninja '
            'v/s Digital-style), so panels value fundamentals, communication, basic project '
            'clarity and whether the candidate will stay and adapt. Recruiters probe '
            'willingness to relocate, work on client projects, and shift-friendly energy.'
        ),
        'interviewer_style': (
            'Courteous, formal-ish, direct. They check depth of CS fundamentals (OOP, SQL, '
            'DBMS, OS) and gently challenge vague project claims. HR asks motivational and '
            'stability questions in a friendly Tata way.'
        ),
        'question_flavours': [
            'Explain OOPs to me like I am your client, not your professor.',
            'You built X in your project — walk me through the part YOU actually wrote.',
            'If we post you to a client site in another city next month, how would you handle the move?',
            'What is the difference between a primary key and a unique constraint — in one sentence?',
        ],
    },
    'infosys': {
        'keywords': ['infosys', 'infosys'],
        'about': (
            'Infosys is a global IT services and consulting firm headquartered in Bengaluru '
            'with roughly 300,000 employees, known for digital transformation, cloud '
            'modernisation, AI and large enterprise accounts.'
        ),
        'environment': (
            'Professional, structured and focused on upskilling from day one. Panels look for '
            'logical reasoning, communication, programming fundamentals and adaptability to '
            'learn client-facing tech fast. Values honesty in projects and a "willing to '
            'learn anything" attitude over technical grandeur.'
        ),
        'interviewer_style': (
            'Polite, encouraging but probing. Expect scenario questions, pseudo-code, and '
            'follow-ups on anything you claim. They like crisp, structured responses.'
        ),
        'question_flavours': [
            'Tell me about a project where you had to learn a new stack quickly. How did you do it?',
            'Write the logic — not the code — for finding duplicate values in an array.',
            'Describe your last team disagreement and how you handled it.',
            'Why Infosys over a startup, honestly?',
        ],
    },
    'wipro': {
        'keywords': ['wipro'],
        'about': (
            'Wipro is a leading Indian IT services and consulting company (headquartered in '
            'Bengaluru) that also builds cloud, engineering, AI and cybersecurity solutions '
            'for global clients.'
        ),
        'environment': (
            'Practical and outcome-focused. Fresher rounds dig deeply into projects regardless '
            'of track, so the panel expects you to defend what is on your resume line by line. '
            'Famous for checking fundamentals (OOP, SQL joins, DBMS, Java internals) and the '
            'ability to explain things in plain English. Location and shift flexibility matter.'
        ),
        'interviewer_style': (
            'Calm but exacting. They re-read your resume and interrogate every bullet. '
            'Appreciates candidates who say "I don\'t know" honestly rather than bluff.'
        ),
        'question_flavours': [
            'Explain how a HashMap works to a non-technical client.',
            'This SQL query has a problem — where and why?',
            'What part of your project did you struggle with the most, honestly?',
            'Write a query for the second-highest salary without ORDER BY LIMIT tricks.',
        ],
    },
    'hcl': {
        'keywords': ['hcl', 'hcltech'],
        'about': (
            'HCLTech is a multinational IT services and engineering firm (part of the HCL '
            'Group) spanning software, infrastructure, cloud, engineering services and '
            'digital products for global enterprises.'
        ),
        'environment': (
            'Energetic, growth-focused and idea-friendly (HCL jokes about applying an '
            '"Ideapreneurship" mindset). Panels value strong communication, web and '
            'enterprise tech fundamentals, real project work and a self-starter tone. '
            'Fresher roles stress trainability and positive energy.'
        ),
        'interviewer_style': (
            'Brisk, upbeat, practical. Likes candidates who think on their feet and show '
            'genuine interest in technology beyond the syllabus.'
        ),
        'question_flavours': [
            'If you were given a new tech to learn in one week for a client, what is your plan?',
            'Explain REST APIs to a non-developer in two sentences.',
            'Tell me about a time you came up with an idea no one asked you for.',
            'Where do you see yourself, realistically, two years after joining?',
        ],
    },
    'accenture': {
        'keywords': ['accenture'],
        'about': (
            'Accenture is a global professional services company combining strategy, '
            'consulting, digital, technology and operations, with a massive India delivery '
            'footprint (Accenture India).'
        ),
        'environment': (
            'Fast-paced, consulting-style, client-first. Panels look for communication, '
            'analytical thinking, technology fundamentals (Java, Python, C++, web basics), '
            'and the confidence to present ideas clearly to senior stakeholders. Global '
            'mindset and "can do" energy are heavily weighted.'
        ),
        'interviewer_style': (
            'Corporate-friendly but sharp. They test how you structure thoughts, handle '
            'client-like scenarios, and whether you can think about business impact, not '
            'just code.'
        ),
        'question_flavours': [
            'A client requests a feature you think is a bad idea. How do you handle it?',
            'Summarise your final-year project in 30 seconds as if pitching to a client.',
            'What is the business value of what you built — beyond grades?',
            'Walk me through a time you influenced a decision you had no authority over.',
        ],
    },
    'cognizant': {
        'keywords': ['cognizant', 'cts'],
        'about': (
            'Cognizant is a global IT services company headquartered in Teaneck, NJ with a '
            'huge India delivery center presence, serving banking, healthcare, retail and '
            'manufacturing clients with digital engineering and consulting.'
        ),
        'environment': (
            'Delivery-focused and practical. Fresher panels concentrate on communication, '
            'SQL/database reasoning, core programming, and attitude. They reward candidates '
            'who listen carefully, answer exactly what is asked, and behave like dependable '
            'client-facing professionals.'
        ),
        'interviewer_style': (
            'Professional, structured, slightly brisk. Values precise answers over lengthy '
            'explorations and calm manners under questions.'
        ),
        'question_flavours': [
            'A client is upset about a delay — how do you respond in the first conversation?',
            'What is the difference between join and subquery performance-wise?',
            'Tell me about a commitment you honoured even when it was inconvenient.',
            'Why should we select you over a classmate with better grades?',
        ],
    },
    'capgemini': {
        'keywords': ['capgemini'],
        'about': (
            'Capgemini is a French-founded global IT services and consulting company with a '
            'large India presence, known for AI, cloud, engineering and business '
            'transformation work across every major industry.'
        ),
        'environment': (
            'Cultured, collaborative and consultant-grade. Panels look for strong logical '
            'reasoning, verbal skill, project explainability and the polish to represent '
            'clients. Gurukul-onboarding culture means they hire for potential and then '
            'train heavily, so sincerity and fundamentals matter more than buzzwords.'
        ),
        'interviewer_style': (
            'Calm, professional, conversational. Likes structured STAR-ish answers and '
            'honest "here is what I would learn next" admissions.'
        ),
        'question_flavours': [
            'Give me one logical puzzle-style problem and your step-by-step thinking.',
            'What does "client-ready" mean to you?',
            'Tell me a time you explained something technical to a non-technical person.',
            'Choose one tech to master this year — why that one?',
        ],
    },
    'deloitte': {
        'keywords': ['deloitte', 'delloitte'],
        'about': (
            'Deloitte is one of the Big Four professional services firms, offering audit, tax, '
            'consulting, advisory and technology services globally, with major offices and '
            'analytics hubs across India.'
        ),
        'environment': (
            'Professional services polish: structured thinking, ethics, client rapport, and '
            'the ability to manage ambiguity. Panels value communication, business sense, '
            'data reasoning, and integrity-flavoured behavioural answers. Expect '
            '"why consulting at Deloitte" style motivation checks.'
        ),
        'interviewer_style': (
            'Refined, scenario-driven, quietly rigorous. They probe how you prioritise, '
            'manage stakeholders and stay ethical under pressure.'
        ),
        'question_flavours': [
            'A client asks you to adjust a number to look better. What do you do?',
            'Walk me through how you would break down an unfamiliar business problem.',
            'Tell me about a time you had to deliver bad news professionally.',
            'Why services over product companies?',
        ],
    },
    'kpmg': {
        'keywords': ['kpmg'],
        'about': (
            'KPMG is a Big Four professional services firm spanning audit, tax and advisory, '
            'operating major delivery and analytics centres in India.'
        ),
        'environment': (
            'Principles-first and detail-obsessed. Panels look for logical sharpness, '
            'financial/data literacy, structured communication and the composure to handle '
            'high-pressure client situations. Integrity jokes are not optional here — '
            'ethical judgement IS the job.'
        ),
        'interviewer_style': (
            'Formal yet friendly, with pointed "how would you actually do that" follow-ups '
            'that test real reasoning rather than rehearsed answers.'
        ),
        'question_flavours': [
            'How would you validate a claim before putting it in a report?',
            'Tell me about a time you caught your own mistake at the last moment.',
            'Two deliverables, same deadline, one resource — what is your logic?',
            'If a senior asks you to skip a process step, what do you do?',
        ],
    },
    'ey': {
        'keywords': ['ey', 'ernst young'],
        'about': (
            'EY (Ernst & Young) is a Big Four firm offering assurance, tax, strategy and '
            'transactions services, with large India operations and technology/analytics teams.'
        ),
        'environment': (
            'Client-facing, deadline-driven and collaborative. Panels probe communication, '
            'logical clarity, risk-awareness and whether the candidate can ask smart '
            'questions. "Voice your thinking out loud" is a genuine hiring theme here.'
        ),
        'interviewer_style': (
            'Encouraging but testy on reasoning chains — they want to hear your logic, not '
            'just your conclusion.'
        ),
        'question_flavours': [
            'What are the risks if we ship this without testing?',
            'Explain your thought process while solving an MCQ: why did you eliminate each option?',
            'Tell me about a time you defended your work to someone senior.',
            'How would you explain a complex concept to a client who is in a hurry?',
        ],
    },
    'pwc': {
        'keywords': ['pwc', 'price waterhouse'],
        'about': (
            'PwC is a global professional services network known for assurance, advisory and '
            'tax work, with a substantial technology and consulting presence in India.'
        ),
        'environment': (
            'Purpose-led and people-focused, but rigorous on delivery. Panels assess '
            'analytical skill, communication polish, stakeholder judgement and learning '
            'agility. Expect questions that tie your project experience to business outcomes.'
        ),
        'interviewer_style': (
            'Warm, deliberate and very structured. They reward candidates who organise '
            'answers clearly and own their growth areas.'
        ),
        'question_flavours': [
            'Describe a project in three layers: what it was, what you did, what you learned.',
            'How do you decide when to ask for help vs figure it out yourself?',
            'What does integrity look like on a typical Tuesday?',
            'Tell me about a time you turned feedback into a real improvement.',
        ],
    },
    'amazon': {
        'keywords': ['amazon', 'aws'],
        'about': (
            'Amazon is a global e-commerce, cloud (AWS) and AI company obsessed with '
            'customers, running a large technology workforce in India across retail, devices '
            'and cloud.'
        ),
        'environment': (
            'Obsessively customer-first with 16 written Leadership Principles and a Bar '
            'Raiser in every loop. Interviewers are trained to evaluate behavioural '
            '"tell me about a time" questions via STAR, seek real numbers/metrics, and judge '
            'default-duck decision-making. No brainteasers. Data-driven, ownership-obsessed, '
            'day-one energy.'
        ),
        'interviewer_style': (
            'Friendly on the surface, laser-focused underneath. They take scrupulous STAR '
            'notes and will politely insist "what was YOUR role, not the team\'s?".'
        ),
        'question_flavours': [
            'Tell me about a time you disagreed with your manager — what happened, what did you do?',
            'Give me a situation where you were wrong, with the actual number attached.',
            'How would you decide between shipping now with a bug or delaying for quality?',
            'Tell me about a customer problem you solved that nobody asked you to solve.',
        ],
    },
    'google': {
        'keywords': ['google', 'goog', 'alphabet'],
        'about': (
            'Google (Alphabet) builds the world\'s leading search engine, mobile OS, cloud '
            'and AI products, with major engineering and product offices in India '
            '("Googlers" in Bengaluru, Hyderabad, Gurugram).'
        ),
        'environment': (
            "Knowledge workers' paradise: ambiguity-tolerant, feedback-loving, hugely "
            'collaborative. Interviews assess problem-solving thought-process (not just the '
            'final answer), leadership, job-relevant knowledge and "Googleyness" — humility, '
            'fun, ownership, comfort with ambiguity. Interviewers literally want to hear '
            'your thinking out loud.'
        ),
        'interviewer_style': (
            'Relaxed, friendly, genuinely trying to help you succeed. They love it when you '
            'talk while solving, test edge cases, and admit trade-offs gracefully.'
        ),
        'question_flavours': [
            'Walk me through how you would build a feature and every trade-off you make.',
            'Tell me about a time you changed your mind based on new information.',
            'Design something that handles ambiguity — how do you even start?',
            'What is something hard you taught yourself, and how did you do it?',
        ],
    },
    'microsoft': {
        'keywords': ['microsoft'],
        'about': (
            'Microsoft is a global technology company behind Windows, Office/365, Azure '
            'cloud, LinkedIn and AI (Copilot), with large India engineering centres in '
            'Bengaluru and Hyderabad.'
        ),
        'environment': (
            'Growth-mindset culture ("learn it all, not know it all"). Panels want real '
            'coding, system-thinking for scale, and collaboration stories. They explicitly '
            'test how you behave when you do NOT know something. Structure over hype, '
            'clarity over speed.'
        ),
        'interviewer_style': (
            'Professional, engineering-serious but humane. They give hints and genuinely '
            'reward how you take them.'
        ),
        'question_flavours': [
            'Write code for X; now make it handle one billion users.',
            'Tell me about a time you learned a technology because a project demanded it.',
            'How do you design an API your teammates will not hate?',
            'What happens when your best idea fails in front of everyone?',
        ],
    },
    'ibm': {
        'keywords': ['ibm'],
        'about': (
            'IBM is a global enterprise tech and AI company (watsonx, hybrid cloud, '
            'consulting) with major labs and delivery offices across India.'
        ),
        'environment': (
            'Thinking-partner culture: system design, industry solutions, enterprise '
            'grade. Panels assess logical reasoning, tech fundamentals, communication and '
            'whether you can operate in a globally distributed, consulting-y ecosystem. '
            'Precision and follow-through are watched closely.'
        ),
        'interviewer_style': (
            'Composed, systemic, occasionally philosophical. They like layered answers: '
            'what, why, and how you would scale it.'
        ),
        'question_flavours': [
            'Walk me through what happens when a user types a URL — briefly.',
            'Tell me about a time you debugged something with almost no clues.',
            'What does "enterprise grade" mean to you?',
            'How would you explain AI to your grandparents?',
        ],
    },
    'techmahindra': {
        'keywords': ['tech mahindra', 'mahindra tech', 'techmahindra'],
        'about': (
            'Tech Mahindra is a leading Indian IT and BPO services company (Mahindra group) '
            'heavily focused on telecom, automotive, enterprise digital and AI solutions.'
        ),
        'environment': (
            'Down-to-earth, delivery-focused and people-friendly. Panels test fundamentals, '
            'communication, project honesty and coachability. Extravershifts are common, '
            'so flexibility and team temperament matter. "Dare to try" is the company '
            'motto — they like doers, not overthinkers.'
        ),
        'interviewer_style': (
            'Warm and practical. They value clear, honest answers and real examples over '
            'impressive-sounding claims.'
        ),
        'question_flavours': [
            'Tell me about a time you tried something and failed — what did it teach you?',
            'Explain how you would onboard a client to your project in plain words.',
            'What is your strongest core CS subject, and prove it with one example?',
            'Are you ready for technology that changes every year? How do you keep up?',
        ],
    },
    'lti': {
        'keywords': ['lti', 'mindtree', 'ltimindtree'],
        'about': (
            'LTIMindtree is a major global IT consulting and digital solutions company born '
            'from the LTI and Mindtree merger, serving banking, hi-tech and retail clients.'
        ),
        'environment': (
            'Agile-first, engineering-focused and collaborative. Panels look for strong basics, '
            'clear communication, and a real build-things portfolio — projects matters. They '
            'reward thinking about maintainability and teams, not just "it runs on my PC".'
        ),
        'interviewer_style': (
            'Friendly-engineering: they like design discussions and tests whether you can '
            'reason about your own code like a professional.'
        ),
        'question_flavours': [
            'What makes code maintainable, concretely?',
            'Explain your project\'s architecture in three layers.',
            'How do you handle a teammate whose code is breaking the build?',
            'What would you automate first in a manual process?',
        ],
    },
    'persistent': {
        'keywords': ['persistent'],
        'about': (
            'Persistent Systems is a Pune-headquartered product engineering and digital '
            'transformation company building tech for leading software and enterprise clients.'
        ),
        'environment': (
            'Engineer-culture: product thinking, code quality and practical problem-solving '
            'are everything. Panels probe language fundamentals, design sense and how '
            'thoroughly you test your own work. Enthusiasm for shipping good software reads '
            'loudly here.'
        ),
        'interviewer_style': (
            'Sharp, hands-on, code-first. They may ask you to write and reason about code '
            'on the spot over discussing theory.'
        ),
        'question_flavours': [
            'Write a small function and tell me all the edge cases you handled.',
            'What is the worst bug you have fixed and how did you trace it?',
            'How do you decide a project is "done"?',
            'Refactor this messy code — what do you prioritise?',
        ],
    },
    'zoho': {
        'keywords': ['zoho'],
        'about': (
            'Zoho is a bootstrapped Chennai-based SaaS company building a 55+ product '
            'suite (CRM, collaboration, finance) used by tens of millions of users worldwide.'
        ),
        'environment': (
            'Engineer-first, debt-free, product-obsessed and proudly unconventional. Zoho '
            'hires for aptitude and attitude over degree brand; interviews are '
            'conversation-heavy, puzzle-light, and culture-fit matters enormously. Slow '
            'careful thinking beats fast answers. Personal projects carry heavy weight.'
        ),
        'interviewer_style': (
            'Relaxed, curious, deeply technical-with-a-personality. They genuinely chat and '
            'want to know how you think and what you build for fun.'
        ),
        'question_flavours': [
            'What do you build when nobody is grading you?',
            'Design a small tool you would actually use yourself.',
            'Why do you think Zoho competes with big SaaS giants?',
            'Talk me through your best piece of code, line by line.',
        ],
    },
    'freshworks': {
        'keywords': ['freshworks', 'freshdesk', 'freshchat'],
        'about': (
            'Freshworks is a Chennai-headquartered SaaS company (in Delightful enterprise '
            'software for customer and employee support: Freshdesk, Freshservice) listed on '
            'the Nasdaq.'
        ),
        'environment': (
            'Customer-obsessed, fast-moving, startup-vibe-with-scale. Panels like ownership, '
            'product sense and honest experimentation. They look for "delightful" communication '
            'and candidates who think about the user before the code.'
        ),
        'interviewer_style': (
            'Energetic, product-first, informal-but-precise. Expect "how would you improve '
            'this product" style thinking.'
        ),
        'question_flavours': [
            'Pick any app you love — what would you improve first and why?',
            'Tell me about a time you acted on user feedback.',
            'What makes software feel delightful to use?',
            'How do you prioritise when your product roadmap beats the deadline?',
        ],
    },
    'flipkart': {
        'keywords': ['flipkart'],
        'about': (
            'Flipkart is India\'s leading e-commerce marketplace (part of the Walmart group) '
            'running everything from shopping app to payments and supply chain tech at huge scale.'
        ),
        'environment': (
            'High-ownership, high-voltage product culture. Panels value DSA and system '
            'thinking for roll-the-scale problems, plus leadership behaviours like bias for '
            'action, customer-obsession and working backwards from the buyer. Expect design '
            'and behavioural rounds with Indian marketplace realism.'
        ),
        'interviewer_style': (
            'Friendly but intense. They chase "how would this behave for 100M users" and '
            '"what does the customer actually feel" with equal energy.'
        ),
        'question_flavours': [
            'How would you design a recommendation surface for Indian shoppers?',
            'Tell me about a time you prioritised speed over perfection and it paid off.',
            'What is the difference between owning a feature and being a bystander in it?',
            'Design a delivery promise estimator — what data would you use?',
        ],
    },
    'myntra': {
        'keywords': ['myntra'],
        'about': (
            'Myntra is India\'s largest fashion e-commerce company (Flipkart group), '
            'engineering everything from trend discovery to RTS fulfilment and virtual '
            'try-ons for Gen-Z shoppers.'
        ),
        'environment': (
            'Fashion-tech energy: taste, data and speed collide. Panels want sharp product '
            'sense for consumer behaviour, solid engineering fundamentals, and the ability '
            'to balance creative sells with hard numbers. Culture is youthful, trend-aware '
            'and aspirational.'
        ),
        'interviewer_style': (
            'Modern, engaged, consumer-mindset-first. They reward ideas grounded in real '
            'shopper behaviour, not textbook features.'
        ),
        'question_flavours': [
            'How would you make a 19-year-old in Tier-2 India buy her first pair of sneakers on Myntra?',
            'What metric would you watch to launch a new collection?',
            'Tell me about a time you understood a user you had nothing in common with.',
            'Design a feature that reduces returns without hurting sales.',
        ],
    },
    'paytm': {
        'keywords': ['paytm', 'one97'],
        'about': (
            'Paytm (One97 Communications) is a leading Indian payments and financial services '
            'company spanning wallets, UPI, merchant payments, lending and wealth at massive scale.'
        ),
        'environment': (
            'Massive-scale consumer fintech: reliability, security and speed under one roof. '
            'Panels test system design for millions of transactions, attention to edge cases '
            'in money flows, and compliance-aware instincts. Volume-work and hustle are part '
            'of the deal; ownership is expected early.'
        ),
        'interviewer_style': (
            'Fast, pragmatic, scenario-heavy. They love "what happens when this fails at 2 AM '
            'on a festival night" questions.'
        ),
        'question_flavours': [
            'Walk me through what happens from tap-to-pay to merchant confirmation.',
            'Design payment retries so we never double-charge a user.',
            'Tell me about a time you held the fort when something broke.',
            'How do you handle a customer\'s money with a system that has 0.001% failure?',
        ],
    },
    'phonepay': {
        'keywords': ['phonepe'],
        'about': (
            'PhonePe is a major Indian payments and financial services platform (Walmart '
            'group) processing billions of UPI transactions through a network of millions '
            'of merchants.'
        ),
        'environment': (
            'Reliability-royalty: uptime is identity. Panels want crisp system design, deep '
            'distributed-systems intuition (idempotency, ordering, exactly-once), and '
            'calmness about money-flow edge cases. Buttons must never double-tap. Culture '
            'is high-performance and values the "build like the whole country runs on it" '
            'mindset.'
        ),
        'interviewer_style': (
            'Technical, precise, and wonderfully concrete — they will simulate a transaction '
            'failure and ask you to walk recovery.'
        ),
        'question_flavours': [
            'Design idempotency for a UPI payment call.',
            'Order of events: what if debit succeeds but credit fails?',
            'Tell me about a time you built reliability into something unreliable.',
            'How would you test a money feature at midnight on Diwali?',
        ],
    },
    'razorpay': {
        'keywords': ['razorpay', 'juspay'],
        'about': (
            'Razorpay (and peers like Juspay) build India\'s payments infrastructure — the '
            'API plumbing that powers checkout, sub-merchants, recurring billing and '
            'banking rails for thousands of businesses.'
        ),
        'environment': (
            'Infrastructure-nerd heaven: lean teams solving gnarly distributed-systems '
            'problems at national scale. Panels prize system design fundamentals, clean '
            'code, and a startup ownership spirit. "Startup energy, enterprise reliability" '
            'is the brief, plus a good sense of humour under pressure.'
        ),
        'interviewer_style': (
            'Sharp, hands-on, merry. They go from "how does money move" to "write this '
            'handler" quickly and enjoy candidates who debate trade-offs out loud.'
        ),
        'question_flavours': [
            'Design a webhook retry system for millions of merchants.',
            'What happens to a payment when our database is down?',
            'Tell me about the hardest bug you traced across systems, not just code.',
            'How would you make a 99.99% uptime promise feel personally yours?',
        ],
    },
    'swiggy': {
        'keywords': ['swiggy', 'zomato'],
        'about': (
            'Swiggy (and rival Zomato) run India\'s giant food-delivery marketplaces — '
            'hyper-local logistics, discovery, and commerce platforms with app-obsessed '
            'Indian consumers.'
        ),
        'environment': (
            'High-velocity consumer tech: 30-minute promise, peak-hour bursts, messy '
            'real-world data. Panels want product sense for India\'s appetite, system design '
            'for geo/scaling problems, and hustle plus ownership stories. They also love '
            'candidates with opinions on food (it breaks ice instantly).'
        ),
        'interviewer_style': (
            'Playful and sharp. They test calm reasoning under "restaurant is out of biryani '
            'at 1 AM" type stress and reward structured improvisation.'
        ),
        'question_flavours': [
            'How would you estimate delivery time if a rainstorm hits Bengaluru?',
            'Design a peak-hour notification that actually reduces load.',
            'Tell me about a time you improvised your way out of a messy problem.',
            'Why does your favourite dish appear in a food app within 3 seconds of searching?',
        ],
    },
    'jio': {
        'keywords': ['jio', 'reliance'],
        'about': (
            'Reliance Jio is India\'s largest telecom and digital services platform — the '
            'network, apps and devices used by most of the country, plus Jio Platforms\' '
            'tech and media stack.'
        ),
        'environment': (
            'Scale-is-the-product: countries worth of users, real devices, real towers. '
            'Panels value networking fundamentals, telecom/data systems thinking, '
            'cost-conscious engineering (frugality at Indian scale) and the patience for '
            'long-haul operations work. Communication to partners and customers counts.'
        ),
        'interviewer_style': (
            'Practical, substantial, occasionally technical-grilling. They like '
            '"explain it to a kiosk owner in a village" energy.'
        ),
        'question_flavours': [
            'Explain what happens when a village user\'s phone connects for the first time.',
            'How would you keep a network feature working when 10x users arrive overnight?',
            'Tell me about a time you made a complex thing simple.',
            'What does "affordable scale" mean in engineering?',
        ],
    },
    'tata': {
        'keywords': ['tata', 'tata motors', 'tata consultancy', 'tata steel'],
        'about': (
            'The Tata group spans TCS, Tata Motors, Tata Steel, Tata Electronics and more — '
            'India\'s most trusted corporate family, with values as famous as its products.'
        ),
        'environment': (
            'Values-first corporate India: integrity, teamwork and long-term thinking over '
            'short-term fireworks. Panels probe character ("a Tata person"), stability, '
            'humility and willingness to serve the organisation — not just flashy skills. '
            'Professional warmth over aggressive salesmanship.'
        ),
        'interviewer_style': (
            'Cultured, dignified, softly probing. They read between the lines of '
            '"why Tata" and appreciate grounded, sincere answers.'
        ),
        'question_flavours': [
            'What does integrity mean when nobody is watching?',
            'Tell me about a time you put the team\'s win ahead of your own.',
            'Why Tata, and what values do you already live by?',
            'How would you handle being given a task you think is below your potential?',
        ],
    },
    'walmart': {
        'keywords': ['walmart', 'meesho'],
        'about': (
            'Walmart runs one of the world\'s largest retail, financial services and e-commerce '
            'engines, with a major global tech presence in India (and partners like Flipkart/PhonePe).'
        ),
        'environment': (
            'Low-cost-leader retail thinking: efficiency, savings for the customer, supply '
            'chain muscle and data everywhere. Panels want cost-conscious engineering, '
            'ownership, and practical "does this actually save people money" sense. '
            'Humility and service posture are big.'
        ),
        'interviewer_style': (
            'Down-to-earth, data-oriented and unfancy. They reward simple scalable solutions '
            'over clever ones.'
        ),
        'question_flavours': [
            'How would you cut 5% off a delivery cost without hurting speed?',
            'Tell me about a time you finished something that was "someone else\'s job".',
            'What is a small change that would improve shopping for a low-budget customer?',
            'Explain how good data tells you whether a price cut worked.',
        ],
    },
    'oracle': {
        'keywords': ['oracle'],
        'about': (
            'Oracle is a global database, cloud (OCI) and enterprise applications company '
            'with large engineering centres in India building the systems the world\'s '
            'companies run on.'
        ),
        'environment': (
            'Enterprise-grade and database-serious. Panels test SQL deeply, system/scale '
            'instincts, and patience for long-lived enterprise products. Values fundamental '
            'computer science, exactness and being reliable over being flashy.'
        ),
        'interviewer_style': (
            'Thorough, technical, low-drama. They respect precise definitions and rigorous '
            'reasoning over enthusiasm alone.'
        ),
        'question_flavours': [
            'Indexes: when do they help and when do they backfire?',
            'Design a system that guarantees zero data loss on a single machine.',
            'Tell me about the largest dataset you have ever worked with and what you learned.',
            'What is the difference between a transaction and a locked table, in plain words?',
        ],
    },
    'salesforce': {
        'keywords': ['salesforce'],
        'about': (
            'Salesforce is the global leader in customer relationship management and cloud '
            'SaaS, with substantial engineering presence in India building Enterprise '
            'features behind the #1 CRM (and now Agentforce AI).'
        ),
        'environment': (
            'Customer-success culture on multi-tenant cloud scale — a shared infrastructure '
            'where one bad query affects everyone. Panels value distributed-systems '
            'thinking, multi-tenancy awareness, test-driven practices and "Ohana" '
            'friendliness — be technically strong without being a jerk.'
        ),
        'interviewer_style': (
            'Warm, collaborative, and remarkably kind while still being rigorous about '
            'scalability and design choices.'
        ),
        'question_flavours': [
            'Your code runs in the same box as 10,000 other customers — what changes in how you build?',
            'Design a feature so one noisy customer cannot affect anyone else.',
            'Tell me about a time you helped a colleague win over helping yourself.',
            'Write a test for something that is "hard to test" and say why it matters.',
        ],
    },
    'netflix': {
        'keywords': ['netflix'],
        'about': (
            'Netflix runs the world\'s leading streaming platform with recommendation systems, '
            'encoding pipelines and a unique TV-engineering culture, plus a small but mighty '
            'India tech presence.'
        ),
        'environment': (
            '"Freedom & Responsibility" — high-performance culture with little process and '
            'enormous trust. Interviews test adulthood: clear ownership, judgement in '
            'ambiguity, candid feedback and taste (they literally ask design/opinion '
            'questions). No micromanagement anywhere; candour is a feature.'
        ),
        'interviewer_style': (
            'Thoughtful, opinionated, peer-like. They enjoy genuine point-of-view debates '
            'and respect candidates who push back with logic.'
        ),
        'question_flavours': [
            'Tell me about a time you made a judgement call with no one to ask.',
            'What makes a recommendation feel magical vs annoying?',
            'When should a high-performing team remove somebody?',
            'Give me an honest, hard-hitting piece of feedback you once received.',
        ],
    },
    'meta': {
        'keywords': ['meta', 'facebook', 'instagram', 'whatsapp'],
        'about': (
            'Meta builds Instagram, WhatsApp, Facebook and the AI tools behind them, with '
            'significant India engineering teams serving billions messaging and social users.'
        ),
        'environment': (
            '"Move fast" meets deeply careful systems for billions of Indian users. Panels '
            'want sharp product instinct, strong DSA/system design, and a "build for '
            'everyone" mentality. WhatsApp culture is notoriously reliability-first; '
            'Facebook culture is product-experimentation-first. Both reward ship-it '
            'ownership stories.'
        ),
        'interviewer_style': (
            'Fast-paced, product-passionate, technically exacting but friendly. They engage '
            'with curiosity about scale and user behaviour.'
        ),
        'question_flavours': [
            'Design a system where 1 billion people send messages on a festival day.',
            'How would you make messaging feel instant even on a 2G signal?',
            'Tell me about a time you shipped something fast and fixed it later.',
            'What product would you build for India that Meta is not building?',
        ],
    },
}


GENERIC_FRAMEWORK = (
    'ABOUT THE COMPANY:\n'
    'We do not have detailed research on this company yet, so the panel should fall back '
    'on what it genuinely knows (or can reasonably infer) about {company}: its industry, '
    'the products or services it is known for, its size and where it operates. If the '
    'model has real knowledge of this company, it should absolutely use it.\n\n'
    'WORK ENVIRONMENT — USE THE BEST-FIT FRAMEWORK:\n'
    '- Large IT services / enterprise consulting: client-ready communication, solid '
    'fundamentals (OOP, SQL, DBMS, basic DSA), project depth, teamwork, learning agility, '
    'willingness to work across domains/teams.\n'
    '- Product / technology company: problem-solving and design thinking, ownership, '
    'product sense, code quality, how the candidate handles ambiguity and trade-offs.\n'
    '- Startup / fast-growth: speed, ownership, comfort with ambiguity, generalist '
    'attitude, high energy, willingness to wear many hats.\n'
    '- Bank / finance / payments: accuracy, integrity, logical reasoning, risk-awareness, '
    'process discipline, calmness under money-scale stakes.\n'
    '- Retail / consumer / e-commerce: customer empathy, efficiency, data-driven thinking, '
    'practical simplification under scale.\n\n'
    'INTERVIEWER PERSONA & FLAVOUR:\n'
    'Play the kind of interviewer that company would realistically field. Mirror their '
    'formality level, their favourite competencies, and the flavour of questions they ask '
    'for a {role} role. Keep it authentic and specific to that workplace, never generic-bot.'
)


def _normalize(name):
    """Lowercase, strip punctuation, and collapse whitespace for matching."""
    text = re.sub(r'[^a-z0-9 ]', ' ', (name or '').lower())
    return ' '.join(text.split())


def find_company_insight(company_name):
    """Return the insight entry nearest to ``company_name``, or None.

    Matching is greedy: if any keyword appears anywhere in the normalized company
    name (or vice-versa), that entry wins.
    """
    name = company_name or ''
    norm = _normalize(name)
    if not norm:
        return None
    tokens = set(norm.split())
    best = None
    best_score = 0
    for key, entry in COMPANY_INSIGHTS.items():
        keywords = [key] + list(entry.get('keywords', []))
        for kw in keywords:
            kw_norm = _normalize(kw)
            if not kw_norm:
                continue
            if norm == kw_norm or kw_norm in norm or norm in kw_norm:
                score = len(kw_norm.split())
            else:
                kw_tokens = set(kw_norm.split())
                overlap = len(tokens & kw_tokens)
                score = overlap if overlap >= 2 else 0
            if score > best_score:
                best_score = score
                best = entry
                if kw_norm in norm or norm in kw_norm:
                    return best
    return best


def company_context_block(company_name):
    """A formatted research brief for the mock-interview panel about ``company_name``.

    Uses curated data when available, otherwise a generic best-fit framework so the
    interview still builds a believable environment for the company.
    """
    company = company_name or 'this company'
    entry = find_company_insight(company_name)
    if entry is None:
        return (
            '\n\n--- {COMPANY} — COMPANY & ENVIRONMENT BRIEF (GENERIC FRAMEWORK) ---\n'
            + GENERIC_FRAMEWORK.replace('{company}', company)
            + ('\n  Target role: {role}.' if '{role}' in GENERIC_FRAMEWORK else '')
            + '\n'
            'IMPORTANT: Fold this into the interview naturally — set the room, mirror the '
            'company vibe, and ground questions in that workplace. Never lecture the '
            'candidate about the company; let it feel like a real interview happening '
            'inside it.\n'
        )
    flavours = '\n'.join(f'- {q}' for q in entry['question_flavours'])
    return (
        f'\n\n--- {company.upper()} — COMPANY & ENVIRONMENT BRIEF ---\n'
        f'ABOUT THE COMPANY:\n{entry["about"]}\n\n'
        f'WORK ENVIRONMENT & HOW THEY HIRE:\n{entry["environment"]}\n\n'
        f'INTERVIEWER PERSONA AT THIS COMPANY:\n{entry["interviewer_style"]}\n\n'
        'FLAVOUR QUESTIONS THIS COMPANY PLAYS WITH (adapt freely, do not read verbatim):\n'
        f'{flavours}\n\n'
        'IMPORTANT: Fold this into the interview naturally — set the room the candidate '
        'would actually walk into, mirror the company\'s real vibe, and ground questions '
        'in this company\'s world. Never lecture the candidate about the company; let it '
        'feel like a real interview happening inside it.'
    )