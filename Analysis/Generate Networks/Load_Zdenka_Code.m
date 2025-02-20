% 20/04/19
% Loading Function for Zdenka's Code v1.0

function [network, sim_loaded, explore_network, numNetworks] = Load_Zdenka_Code(varargin)
%% Load Network Data:
%choose network to load
if ~isempty(varargin)
    biasType=varargin{2};
end
computer=getenv('computername');
switch computer
    case 'W4PT80T2'
        dataPath='C:\Users\aloe8475\Documents\PhD\GitHub\CODE\Data\Raw\Networks\Zdenka Networks';
        simPath='C:\Users\aloe8475\Documents\PhD\GitHub\CODE\Data\Raw\Simulations\Zdenka';
    case ''
%         dataPath='/import/silo2/aloe8475/Documents/CODE/Data/Raw/Networks/Zdenka Networks/';
        dataPath='/headnode2/aloe8475/CODE/Data/Raw/Networks/Zdenka Networks/';
        if exist('biasType','var')
            switch biasType
                case 'TimeDelay'
                    simPath='/headnode2/aloe8475/CODE/Data/Raw/Simulations/Zdenka/Variable Time Delay/';%'/suphys/aloe8475/Documents/CODE/Data/Raw/Simulations/Zdenka';
%                      simPath='/import/silo2/aloe8475/Documents/CODE/Data/Raw/Simulations/Zdenka/Variable Time Delay/';
                case 'DCandWait'
                    simPath='/headnode2/aloe8475/CODE/Data/Raw/Simulations/Zdenka/10 Square Pulses/';
                case 'DC'
                    simPath='/headnode2/aloe8475/CODE/Data/Raw/Simulations/Zdenka/Single DC Pulse/';
            end
        else
            simPath='/headnode2/aloe8475/CODE/Data/Raw/Simulations/Zdenka/';
% simPath='/import/silo2/aloe8475/Documents/CODE/Data/Raw/Simulations/Zdenka/Variable Time Delay/';
        end 
    case 'LAPTOP-S1BV3HR7'
        dataPath='D:\alon_\Research\PhD\CODE\Zdenka Code\atomic-switch-network-1.3-beta\examples';
end
if isempty(varargin)
    cd(dataPath)
    waitfor(msgbox('Select the Network saved data'));
    [FileName,PathName] = uigetfile('*.mat','Select the Network saved data');
    count=1;
    f{count}=fullfile(PathName,FileName);
    load(f{count});
else
    numNW=varargin{1}(1);
    simNum=varargin{1}(2);
    load([dataPath 'AdriantoZdenka' num2str(numNW) 'nw_simulation1.mat']);
end
% Define network variable
network(count)=SelNet;
clear SelNet
% Delete default simulation data:

numNetworks=1;
i=1;
if isempty(varargin)
    
    more_networks=input('Do you want to load another Network? \n','s');
    if more_networks=='y'
        while i==1
            %Update network count
            count=count+1;
            %prompt for the network .mat file with button
            promptMessage = sprintf('Select the Network saved data');
            button = questdlg(promptMessage, 'Load Network Data', 'OK','Cancel','OK');
            if strcmp(button, 'Cancel')
                numNetworks=count-1; %if they change their mind and cancel, skip to simulations
                break;
            elseif strcmp(button,'OK')
                % if they want a second network, prompt for second network data
                [FileName2,PathName2] = uigetfile('*.mat','Select the Network saved data');
                f{count}=fullfile(PathName2,FileName2);
                if count ~= 1 & sum(~cellfun('isempty',strfind(f,f{count})))>1 %if the current network string occurs more than once
                    %ask them to select a different network
                    waitfor(msgbox('Error: Cannot load same network twice. Please select a different Network'));
                    count=count-1;%reduce our counter because we go back to the start of the while loop.
                    error_state=1;
                else
                    load(f{count});
                    % Define network variable
                    network(count)=SelNet;
                    % save a var with number of networks
                    numNetworks=count;
                    i=i+1; %can also use break
                    error_state=0;
                end
            end
            if error_state~=1 %we don't want to ask to load again if we got an error
                more_networks=input('Do you want to load another Network? \n','s');
            else
                more_networks='y';
            end
            if more_networks=='y'
                i=1;
            end
        end
    end
end

%% Load Simulation Data
if isempty(varargin)
    sims_load=input('Load Simulation Data too? y or n? \n','s');
else
    sims_load='y';
end
if sims_load=='y'

    load_cluster='n'; %Load data from Cluster
    
    % Delete default simulation data:
    network(1).Simulations = [];
    if length(network)>1
        % Delete default simulation data as well:
        network(2).Simulations = [];
    end
    if isempty(varargin)
        explore_network=lower(input('Do you want Training + Testing Data, or Just Explore Data? - T or E \n','s'));
                        fprintf('Loading Network & Simulation Data \n');

    else
        explore_network='e'; %explore only
                        fprintf('Loading Network & Simulation Data \n');

    end
    %Select which Simulation to Load
    sim_loaded=1;
    if explore_network=='t'
        cd('Simulations Only\Training');
        waitfor(msgbox('Select the Training Simulation saved data'))
        [FileName,PathName] = uigetfile('*.mat','Select the Training saved data');
        f=fullfile(PathName,FileName);
        load(f);
        
        %Add simulation data to network struct:
        if numNetworks==2
            training_network=input('Which Network was the Training simulation from? 1 or 2 \n');
        end
        temp1=SelSims;
        
        clear SelSims
        cd('..\Testing');
        waitfor(msgbox('Select the Testing Simulation saved data'))
        [FileNameTest,PathNameTest] = uigetfile('*.mat','Select the Testing saved data');
        f_test=fullfile(PathNameTest,FileNameTest);
        load(f_test);
        
        %Add simulation data to network struct:
        if numNetworks==2
            testing_network=input('Which Network was the Testing simulation from? 1 or 2 \n');
        end
        if exist('SelSims','var') == 1
            temp2 = SelSims;%save simulations from test network if it hasn't been changed
        else
            temp2 = network.Simulations;%save simulations from test network if it has been changed
        end
        
        if numNetworks==1 %if both training and testing are from same networks, just combine the simulations
            network.Simulations=[temp1 temp2];
            for j = 1:length(temp1)
                network.Simulations{j}.Type='Training Simulation'; %label the training sim
                network.numTrainingSims=length(temp1);
            end
            for i=(length(temp1)+1):length(network.Simulations)
                network.Simulations{i}.Type='Testing Simulation';
                network.numTestingSims=length(network.Simulations)-length(temp1);
            end
        elseif numNetworks==2 %if the two networks are different, save the simulations in the different networks
            network(training_network).Simulations=temp1;
            network(testing_network).Simulations=temp2;
            network(training_network).Simulations{1}.Type='Training Simulation'; %label which is the training sim
            network(training_network).Type='Training Network';
            clear SelSims
        end
    else
        if isempty(varargin) %if we don't input a variable
            if load_cluster=='y'
                SelSims=loadSimulationsFromCluster();
            else
                cd(simPath)
                waitfor(msgbox('Select the Simulation saved data'))
                [FileName,PathName] = uigetfile('*.mat','Select the Simulation saved data');
                f_explore=fullfile(PathName,FileName);
                load(f_explore);
            end
        else
            load([simPath 'SelSims_TimeDelay_' num2str(simNum) '.mat']);
        end
        if exist('SelSims','var') == 1
            temp= SelSims;%save simulations from test network if it hasn't been changed
        else
            temp = network.Simulations;%save simulations from test network if it has been changed
        end
        network.Simulations=temp;
%         for i=1:length(network.Simulations)
%             for j = 1:length(network.Simulations)
%             network.Simulations.Type='Explore Simulation';
%             end 
%         end
        %Need to change to only allow explore of 1 network
        clear SelSims;
    end
else
    sim_loaded=0;
    explore_network='e';
end
fprintf('Network and Simulations Loaded \n');
fprintf('\n--------------------------------- \n\n');
end

