# ER Diagrams 

This document contains the complete report for the marketplace schema broken down into functionality-specific ER diagrams. Each section includes the key logic and the Mermaid diagram.

## Table of Contents

1. [ER diagram for complete schema](#complete-er-diagram)
2. [Listing & Categorization Module](#listing--categorization-module)
3. [Transaction & Offers Module (Core Marketplace)](#transaction--offers-module-core-marketplace)
4. [Communication Module](#communication-module)
5. [Engagement Module (Wishes & Watchlist)](#engagement-module-wishes--watchlist)
6. [Moderation & Admin Module](#moderation--admin-module)

---

## 1. ER diagram for complete schema

```mermaid
flowchart LR

%% ------------------------------------------
%% Styling
%% ------------------------------------------
classDef entity fill:#fbfbfd,stroke:#2b2f3a,stroke-width:2px,rx:8,ry:8,font-weight:700;
classDef weakEntity fill:#fbfbfd,stroke:#2b2f3a,stroke-width:6px,rx:8,ry:8,font-weight:700;
classDef relation fill:#f0f4f8,stroke:#3a4350,stroke-width:1px,font-style:italic,rx:6,ry:6;
classDef weakRelation fill:#f0f4f8,stroke:#3a4350,stroke-width:4px,font-style:italic,rx:6,ry:6;
classDef attr fill:#ffffff,stroke:#9aa4b2,stroke-width:1px,rx:30,ry:20;
classDef pk fill:#ffffff,stroke:#6b7280,stroke-width:2px,rx:30,ry:20,font-weight:700;

%% small aesthetic tweaks for node text wrapping (some renderers support)
style MEMBER text-align:center
style LIST text-align:center

%% ------------------------------------------
%% Subgraph: Users
%% ------------------------------------------
subgraph Users["Users"]
    direction TB
    MEMBER[MEMBER]:::entity
    ADMIN[ADMINISTRATOR]:::entity

    M_ID("<u>MemberID</u>"):::pk
    M_Name(Name):::attr
    M_Email(Email):::attr
    M_Ph(ContactNumber):::attr
    M_Dept(Department):::attr
    MEMBER --- M_ID & M_Name & M_Email & M_Ph & M_Dept

    A_ID("<u>AdminID</u>"):::pk
    A_Name(Name):::attr
    A_Email(Email):::attr
    ADMIN --- A_ID & A_Name & A_Email
end

%% ------------------------------------------
%% Subgraph: Listings & Categories
%% ------------------------------------------
subgraph Listings["Listings & Categories"]
    direction TB
    CAT[CATEGORY]:::entity
    LIST[LISTING]:::entity
    IMG[[LISTING_IMAGE]]:::weakEntity

    C_ID("<u>CategoryID</u>"):::pk
    C_Name(Name):::attr
    CAT --- C_ID & C_Name

    L_ID("<u>ListingID</u>"):::pk
    L_Title(Title):::attr
    L_Price(AskingPrice):::attr
    L_Cond(Condition):::attr
    LIST --- L_ID & L_Title & L_Price & L_Cond

    I_ID("<u>ImageID</u>"):::pk
    I_URL(ImageURL):::attr
    IMG --- I_ID & I_URL
end

%% ------------------------------------------
%% Subgraph: Marketplace (Offers / Transactions / Ratings / Wishes)
%% ------------------------------------------
subgraph Marketplace["Marketplace"]
    direction TB
    OFFER[OFFER]:::entity
    TRANS[TRANSACTION]:::entity
    RATE[RATING]:::entity
    WISH[WISH_REQUEST]:::entity

    O_ID("<u>OfferID</u>"):::pk
    O_Bid(OfferedPrice):::attr
    OFFER --- O_ID & O_Bid

    T_ID("<u>TransactionID</u>"):::pk
    T_Price(AgreedPrice):::attr
    TRANS --- T_ID & T_Price

    R_ID("<u>RatingID</u>"):::pk
    R_Star(Stars):::attr
    RATE --- R_ID & R_Star

    W_ID("<u>WishID</u>"):::pk
    W_Desc(ItemDescription):::attr
    WISH --- W_ID & W_Desc
end

%% ------------------------------------------
%% Subgraph: Communication & Notifications
%% ------------------------------------------
subgraph Communication["Messaging & Notifications"]
    direction TB
    THREAD[MESSAGE_THREAD]:::entity
    MSG[[MESSAGE]]:::weakEntity
    NOTIF[NOTIFICATION]:::entity

    Th_ID("<u>ThreadID</u>"):::pk
    THREAD --- Th_ID

    Msg_ID("<u>MessageID</u>"):::pk
    Msg_Txt(MessageText):::attr
    MSG --- Msg_ID & Msg_Txt

    N_ID("<u>NotificationID</u>"):::pk
    N_Title(Title):::attr
    NOTIF --- N_ID & N_Title
end

%% ------------------------------------------
%% Subgraph: Moderation
%% ------------------------------------------
subgraph Moderation["Moderation & Reports"]
    direction TB
    REP[REPORT]:::entity

    Rp_ID("<u>ReportID</u>"):::pk
    Rp_Type(ReportType):::attr
    REP --- Rp_ID & Rp_Type
end

%% ------------------------------------------
%% Relationships (center area) - visually spaced
%% ------------------------------------------
%% spacer nodes to steer layout
sp1([ ]):::attr
sp2([ ]):::attr
sp3([ ]):::attr

%% Core relationships
POSTS{Posts}:::relation
MEMBER ===|1| POSTS
POSTS ---|N| LIST

CLASS{Classifies}:::relation
CAT ---|1| CLASS
CLASS ===|N| LIST

HAS_IMG{Has_Image}:::weakRelation
LIST ===|1| HAS_IMG
HAS_IMG ===|N| IMG

MAKES{Makes}:::relation
MEMBER ---|1| MAKES
MAKES ===|N| OFFER

REC{Receives}:::relation
LIST ---|1| REC
REC ===|N| OFFER

BEC{Becomes}:::relation
OFFER ---|1| BEC
BEC ---|1| TRANS

REV{Reviewed_In}:::relation
TRANS ---|1| REV
REV ---|N| RATE

REQS{Requests}:::relation
MEMBER ---|1| REQS
REQS ===|N| WISH

DISC{Negotiated_In}:::relation
MEMBER ---|1| DISC
LIST ---|1| DISC
DISC ===|N| THREAD

CONT{Contains}:::weakRelation
THREAD ===|1| CONT
CONT ===|N| MSG

FILES{Files}:::relation
MEMBER ---|1| FILES
FILES ===|N| REP

RES{Resolves}:::relation
ADMIN ---|1| RES
RES ---|N| REP

GETS{Receives}:::relation
MEMBER ---|1| GETS
GETS ===|N| NOTIF

WATCH{Watches}:::relation
MEMBER ===|M| WATCH
LIST ===|N| WATCH
W_Add(AddedDate):::attr
W_NotP(NotifyOnPrice):::attr
W_NotS(NotifyOnStatus):::attr
WATCH --- W_Add & W_NotP & W_NotS

FULFILL{Fulfills}:::relation
LIST ---|1| FULFILL
FULFILL ---|1| WISH

%% ------------------------------------------
%% Layout nudges (help Mermaid place things nicely)
%% Use invisible edges to guide spacing (no inline comments)
%% ------------------------------------------
MEMBER --- sp1
sp1 --- OFFER
LIST --- sp2
sp2 --- TRANS
THREAD --- sp3
sp3 --- NOTIF

%% ------------------------------------------
%% Final visual tweaks (explicit node widths/heights where supported)
%% ------------------------------------------
style MEMBER fill:#fffefe,stroke:#2b2f3a,stroke-width:2px
style LIST fill:#fffefe,stroke:#2b2f3a,stroke-width:2px
style OFFER fill:#fffefe,stroke:#2b2f3a,stroke-width:2px
style TRANS fill:#fffefe,stroke:#2b2f3a,stroke-width:2px

```

## Breakdown of Complete Schema into Functionality-Specific ER Diagrams

In this section, we will break down the complete schema into smaller ER diagrams based on specific functionalities. Each diagram will focus on a particular module, providing a clearer understanding of the relationships and entities involved.

## 2. Listing & Categorization Module

**Key Logic:**

* A **Member** posts a **Listing**.
* A **Listing** must belong to a **Category**.
* Categories can have sub-categories (recursive relationship).
* A **Listing** can have multiple **Images** (weak entity).

```mermaid
flowchart TD
        %% --- STYLING ---
        classDef entity fill:#f9f9f9,stroke:#000,stroke-width:2px,rx:5,ry:5;
        classDef weakEntity fill:#f9f9f9,stroke:#000,stroke-width:5px,rx:5,ry:5;
        classDef relation fill:#e0e0e0,stroke:#333,stroke-width:1px,shape:rhombus,font-style:italic;
        classDef weakRelation fill:#e0e0e0,stroke:#333,stroke-width:4px,shape:rhombus,font-style:italic;
        classDef attr fill:#fff,stroke:#333,stroke-width:1px,shape:ellipse;
        classDef pk fill:#fff,stroke:#333,stroke-width:2px,shape:ellipse,text-decoration:underline;

        %% ENTITIES
        MEMBER[MEMBER]:::entity
        LIST[LISTING]:::entity
        CAT[CATEGORY]:::entity
        IMG[[LISTING_IMAGE]]:::weakEntity

        %% RELATIONSHIPS
        POSTS{Posts}:::relation
        CLASS{Classifies}:::relation
        SUBCAT{Has_Sub}:::relation
        HAS_IMG{{Has_Img}}:::weakRelation

        %% CONNECTIONS
        MEMBER ===|1| POSTS
        POSTS ---|N| LIST
        
        CAT ---|1| CLASS
        CLASS ===|N| LIST
        
        CAT ---|1| SUBCAT
        SUBCAT ---|N| CAT

        LIST ===|1| HAS_IMG
        HAS_IMG ===|N| IMG

        %% ATTRIBUTES (Key Selection)
        L_ID(<u>ListingID</u>):::pk
        L_Title(Title):::attr
        L_Price(Price):::attr
        L_Cond(Condition):::attr
        LIST --- L_ID & L_Title & L_Price & L_Cond

        C_ID(<u>CategoryID</u>):::pk
        C_Name(Name):::attr
        CAT --- C_ID & C_Name

        I_ID(<u>ImageID</u>):::pk
        I_URL(URL):::attr
        IMG --- I_ID & I_URL

```

---

## 3. Transaction & Offers Module (Core Marketplace)

**Key Logic:**

* A **Member** (Buyer) makes an **Offer** on a **Listing**.
* If accepted, the **Offer** becomes a **Transaction**.
* Alternatively, a **Listing** can directly generate a **Transaction**.
* Once a **Transaction** is done, users leave a **Rating**.

```mermaid
flowchart TD
        classDef entity fill:#f9f9f9,stroke:#000,stroke-width:2px,rx:5,ry:5;
        classDef relation fill:#e0e0e0,stroke:#333,stroke-width:1px,shape:rhombus,font-style:italic;
        classDef attr fill:#fff,stroke:#333,stroke-width:1px,shape:ellipse;
        classDef pk fill:#fff,stroke:#333,stroke-width:2px,shape:ellipse,text-decoration:underline;

        %% ENTITIES
        MEMBER[MEMBER]:::entity
        LIST[LISTING]:::entity
        OFFER[OFFER]:::entity
        TRANS[TRANSACTION]:::entity
        RATE[RATING]:::entity

        %% RELATIONSHIPS
        MAKES{Makes}:::relation
        REC{Receives}:::relation
        BEC{Becomes}:::relation
        PART{Participates}:::relation
        REV{Reviewed_In}:::relation

        %% CONNECTIONS
        MEMBER ---|1| MAKES
        MAKES ===|N| OFFER
        
        LIST ---|1| REC
        REC ===|N| OFFER

        OFFER ---|1| BEC
        BEC ---|1| TRANS

        MEMBER ---|1| PART
        PART ===|N| TRANS

        TRANS ---|1| REV
        REV ---|N| RATE

        %% ATTRIBUTES
        O_ID(<u>OfferID</u>):::pk
        O_Bid(OfferedPrice):::attr
        OFFER --- O_ID & O_Bid

        T_ID(<u>TransID</u>):::pk
        T_Price(AgreedPrice):::attr
        TRANS --- T_ID & T_Price

        R_ID(<u>RatingID</u>):::pk
        R_Star(Stars):::attr
        RATE --- R_ID & R_Star

```

---

## 4. Communication Module

**Key Logic:**

* A **Message Thread** is specific to a Buyer and a Listing.
* A **Message** is a weak entity (cannot exist without a thread).

```mermaid
flowchart TD
        classDef entity fill:#f9f9f9,stroke:#000,stroke-width:2px,rx:5,ry:5;
        classDef weakEntity fill:#f9f9f9,stroke:#000,stroke-width:5px,rx:5,ry:5;
        classDef relation fill:#e0e0e0,stroke:#333,stroke-width:1px,shape:rhombus,font-style:italic;
        classDef weakRelation fill:#e0e0e0,stroke:#333,stroke-width:4px,shape:rhombus,font-style:italic;
        classDef attr fill:#fff,stroke:#333,stroke-width:1px,shape:ellipse;
        classDef pk fill:#fff,stroke:#333,stroke-width:2px,shape:ellipse,text-decoration:underline;

        %% ENTITIES
        MEMBER[MEMBER]:::entity
        LIST[LISTING]:::entity
        THREAD[MESSAGE_THREAD]:::entity
        MSG[[MESSAGE]]:::weakEntity

        %% RELATIONSHIPS
        DISC{Negotiated_In}:::relation
        CONT{{Contains}}:::weakRelation

        %% CONNECTIONS
        MEMBER ---|1| DISC
        LIST ---|1| DISC
        DISC ===|N| THREAD

        THREAD ===|1| CONT
        CONT ===|N| MSG

        %% ATTRIBUTES
        Th_ID(<u>ThreadID</u>):::pk
        Th_Act(IsActive):::attr
        THREAD --- Th_ID & Th_Act

        Msg_ID(<u>MsgID</u>):::pk
        Msg_Txt(Text):::attr
        Msg_Date(SentDate):::attr
        MSG --- Msg_ID & Msg_Txt & Msg_Date

```

---

## 5. Engagement Module (Wishes & Watchlist)

**Key Logic:**

* **Watchlist:** A Many-to-Many relationship between Member and Listing.
* **Wish Request:** A Member requests an item; a new Listing can fulfill that request.

```mermaid
flowchart TD
        classDef entity fill:#f9f9f9,stroke:#000,stroke-width:2px,rx:5,ry:5;
        classDef relation fill:#e0e0e0,stroke:#333,stroke-width:1px,shape:rhombus,font-style:italic;
        classDef attr fill:#fff,stroke:#333,stroke-width:1px,shape:ellipse;
        classDef pk fill:#fff,stroke:#333,stroke-width:2px,shape:ellipse,text-decoration:underline;

        %% ENTITIES
        MEMBER[MEMBER]:::entity
        LIST[LISTING]:::entity
        WISH[WISH_REQUEST]:::entity

        %% RELATIONSHIPS
        WATCH{Watches}:::relation
        REQS{Requests}:::relation
        FULFILL{Fulfills}:::relation

        %% CONNECTIONS
        %% Watchlist is M:N
        MEMBER ===|M| WATCH
        LIST ===|N| WATCH
        
        %% Wishlist
        MEMBER ---|1| REQS
        REQS ===|N| WISH
        
        LIST ---|1| FULFILL
        FULFILL ---|1| WISH

        %% ATTRIBUTES
        W_ID(<u>WishID</u>):::pk
        W_Desc(Description):::attr
        W_Max(MaxBudget):::attr
        WISH --- W_ID & W_Desc & W_Max

        %% Attributes on Relationship
        Wa_Date(AddedDate):::attr
        WATCH --- Wa_Date

```

---

## 6. Moderation & Admin Module

**Key Logic:**

* **Members** file **Reports** (against listings or other users).
* **Admins** resolve **Reports**.
* **Members** receive **Notifications**.

```mermaid
flowchart TD
        classDef entity fill:#f9f9f9,stroke:#000,stroke-width:2px,rx:5,ry:5;
        classDef relation fill:#e0e0e0,stroke:#333,stroke-width:1px,shape:rhombus,font-style:italic;
        classDef attr fill:#fff,stroke:#333,stroke-width:1px,shape:ellipse;
        classDef pk fill:#fff,stroke:#333,stroke-width:2px,shape:ellipse,text-decoration:underline;

        %% ENTITIES
        MEMBER[MEMBER]:::entity
        ADMIN[ADMINISTRATOR]:::entity
        REP[REPORT]:::entity
        NOTIF[NOTIFICATION]:::entity

        %% RELATIONSHIPS
        FILES{Files}:::relation
        RES{Resolves}:::relation
        GETS{Receives}:::relation

        %% CONNECTIONS
        MEMBER ---|1| FILES
        FILES ===|N| REP

        ADMIN ---|1| RES
        RES ---|N| REP

        MEMBER ---|1| GETS
        GETS ===|N| NOTIF

        %% ATTRIBUTES
        Rp_ID(<u>ReportID</u>):::pk
        Rp_Type(Type):::attr
        Rp_Stat(Status):::attr
        REP --- Rp_ID & Rp_Type & Rp_Stat

        A_ID(<u>AdminID</u>):::pk
        A_Role(Role):::attr
        ADMIN --- A_ID & A_Role

        N_ID(<u>NotifID</u>):::pk
```
