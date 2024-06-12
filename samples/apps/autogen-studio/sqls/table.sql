create table agent
(
    id              int auto_increment
        primary key,
    created_at      datetime default CURRENT_TIMESTAMP                     null,
    updated_at      datetime                                               null,
    user_id         varchar(255)                                           null,
    type            enum ('assistant', 'userproxy', 'groupchat', 'custom') null,
    agent_type_name varchar(255)                                           null,
    config          json                                                   null
);

create table agentlink
(
    parent_id int not null,
    agent_id  int not null,
    primary key (parent_id, agent_id),
    constraint agentlink_ibfk_1
        foreign key (parent_id) references agent (id),
    constraint agentlink_ibfk_2
        foreign key (agent_id) references agent (id)
);

create index agent_id
    on agentlink (agent_id);

create table model
(
    id          int auto_increment
        primary key,
    created_at  datetime default CURRENT_TIMESTAMP null,
    updated_at  datetime                           null,
    user_id     varchar(255)                       null,
    model       varchar(255)                       not null,
    api_key     varchar(255)                       null,
    base_url    varchar(255)                       null,
    api_type    enum ('openai', 'google', 'azure') null,
    api_version varchar(255)                       null,
    description varchar(255)                       null
);

create table agentmodellink
(
    agent_id int not null,
    model_id int not null,
    primary key (agent_id, model_id),
    constraint agentmodellink_ibfk_1
        foreign key (agent_id) references agent (id),
    constraint agentmodellink_ibfk_2
        foreign key (model_id) references model (id)
);

create index model_id
    on agentmodellink (model_id);

create table skill
(
    id          int auto_increment
        primary key,
    created_at  datetime default CURRENT_TIMESTAMP null,
    updated_at  datetime                           null,
    user_id     varchar(255)                       null,
    name        varchar(255)                       not null,
    content     varchar(255)                       not null,
    description varchar(255)                       null,
    secrets     json                               null,
    libraries   json                               null
);

create table agentskilllink
(
    agent_id int not null,
    skill_id int not null,
    primary key (agent_id, skill_id),
    constraint agentskilllink_ibfk_1
        foreign key (agent_id) references agent (id),
    constraint agentskilllink_ibfk_2
        foreign key (skill_id) references skill (id)
);

create index skill_id
    on agentskilllink (skill_id);

create table workflow
(
    id             int auto_increment
        primary key,
    created_at     datetime default CURRENT_TIMESTAMP null,
    updated_at     datetime                           null,
    user_id        varchar(255)                       null,
    name           varchar(255)                       not null,
    description    varchar(255)                       not null,
    type           enum ('twoagents', 'groupchat')    null,
    summary_method enum ('last', 'none', 'llm')       null
);

create table session
(
    id          int auto_increment
        primary key,
    created_at  datetime default CURRENT_TIMESTAMP null,
    updated_at  datetime                           null,
    user_id     varchar(255)                       null,
    workflow_id int                                null,
    name        varchar(255)                       null,
    description varchar(255)                       null,
    constraint session_ibfk_1
        foreign key (workflow_id) references workflow (id)
);

create table message
(
    id             int auto_increment
        primary key,
    created_at     datetime default CURRENT_TIMESTAMP null,
    updated_at     datetime                           null,
    user_id        varchar(255)                       null,
    role           varchar(255)                       not null,
    content        json                               null,
    function_call  json                               null,
    tool_calls     json                               null,
    tool_responses json                               null,
    session_id     int                                null,
    connection_id  varchar(255)                       null,
    meta           json                               null,
    constraint message_ibfk_1
        foreign key (session_id) references session (id)
            on delete cascade
);

create index session_id
    on message (session_id);

create index workflow_id
    on session (workflow_id);

create table workflowagentlink
(
    workflow_id int                                    not null,
    agent_id    int                                    not null,
    agent_type  enum ('sender', 'receiver', 'planner') not null,
    primary key (workflow_id, agent_id, agent_type),
    constraint workflowagentlink_ibfk_1
        foreign key (workflow_id) references workflow (id),
    constraint workflowagentlink_ibfk_2
        foreign key (agent_id) references agent (id)
);

create index agent_id
    on workflowagentlink (agent_id);

